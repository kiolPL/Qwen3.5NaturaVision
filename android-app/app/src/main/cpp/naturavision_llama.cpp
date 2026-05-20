#include <android/log.h>
#include <jni.h>
#include <unistd.h>

#include <algorithm>
#include <cctype>
#include <chrono>
#include <mutex>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

#include "ggml-backend.h"
#include "ggml.h"
#include "llama.h"
#include "mtmd.h"
#include "mtmd-helper.h"

namespace {

constexpr const char * LOG_TAG = "NaturaVisionNative";
constexpr int N_CTX = 1536;
constexpr int N_BATCH = 128;
constexpr int N_UBATCH = 64;
constexpr int IMAGE_MIN_TOKENS = 1;
constexpr int IMAGE_MAX_TOKENS = 32;

std::once_flag g_backend_once;

long long elapsed_ms(std::chrono::steady_clock::time_point start) {
    return std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::steady_clock::now() - start
    ).count();
}

void android_log_callback(enum ggml_log_level level, const char * text, void *) {
    if (level == GGML_LOG_LEVEL_DEBUG) {
        return;
    }
    const int priority = level == GGML_LOG_LEVEL_ERROR ? ANDROID_LOG_ERROR :
        level == GGML_LOG_LEVEL_WARN ? ANDROID_LOG_WARN :
        level == GGML_LOG_LEVEL_INFO ? ANDROID_LOG_INFO :
        ANDROID_LOG_DEBUG;
    __android_log_write(priority, LOG_TAG, text);
}

void throw_illegal_state(JNIEnv * env, const std::string & message) {
    jclass cls = env->FindClass("java/lang/IllegalStateException");
    if (cls != nullptr) {
        env->ThrowNew(cls, message.c_str());
    }
}

std::string jstring_to_string(JNIEnv * env, jstring value) {
    if (value == nullptr) {
        return "";
    }
    const char * chars = env->GetStringUTFChars(value, nullptr);
    if (chars == nullptr) {
        return "";
    }
    std::string result(chars);
    env->ReleaseStringUTFChars(value, chars);
    return result;
}

std::vector<unsigned char> jbyte_array_to_vector(JNIEnv * env, jbyteArray bytes) {
    std::vector<unsigned char> out;
    if (bytes == nullptr) {
        return out;
    }
    const jsize size = env->GetArrayLength(bytes);
    out.resize(static_cast<size_t>(size));
    if (size > 0) {
        env->GetByteArrayRegion(bytes, 0, size, reinterpret_cast<jbyte *>(out.data()));
    }
    return out;
}

int native_thread_count() {
    const long cpu_count = sysconf(_SC_NPROCESSORS_ONLN);
    if (cpu_count <= 0) {
        return 4;
    }
    return std::max(2, std::min(6, static_cast<int>(cpu_count) - 2));
}

std::string format_chat_prompt(
    const llama_model * model,
    const std::string & system_prompt,
    const std::string & user_prompt
) {
    const char * tmpl = llama_model_chat_template(model, nullptr);
    if (tmpl == nullptr) {
        return system_prompt + "\n\n" + user_prompt + "\n";
    }

    llama_chat_message messages[2] = {
        {"system", system_prompt.c_str()},
        {"user", user_prompt.c_str()},
    };

    int32_t needed = llama_chat_apply_template(tmpl, messages, 2, true, nullptr, 0);
    if (needed <= 0) {
        return system_prompt + "\n\n" + user_prompt + "\n";
    }

    std::vector<char> buffer(static_cast<size_t>(needed) + 1);
    int32_t written = llama_chat_apply_template(
        tmpl,
        messages,
        2,
        true,
        buffer.data(),
        static_cast<int32_t>(buffer.size())
    );

    if (written < 0) {
        written = -written;
        buffer.assign(static_cast<size_t>(written) + 1, '\0');
        written = llama_chat_apply_template(
            tmpl,
            messages,
            2,
            true,
            buffer.data(),
            static_cast<int32_t>(buffer.size())
        );
    }

    if (written <= 0) {
        return system_prompt + "\n\n" + user_prompt + "\n";
    }
    return std::string(buffer.data(), static_cast<size_t>(written));
}

std::string token_to_piece(const llama_vocab * vocab, llama_token token) {
    char buffer[256];
    int32_t written = llama_token_to_piece(vocab, token, buffer, sizeof(buffer), 0, false);
    if (written < 0) {
        const int32_t required = -written;
        std::vector<char> dynamic_buffer(static_cast<size_t>(required));
        written = llama_token_to_piece(vocab, token, dynamic_buffer.data(), required, 0, false);
        return written > 0 ? std::string(dynamic_buffer.data(), static_cast<size_t>(written)) : "";
    }
    return written > 0 ? std::string(buffer, static_cast<size_t>(written)) : "";
}

std::vector<llama_token> tokenize_text(
    const llama_vocab * vocab,
    const std::string & text,
    bool add_special
) {
    std::vector<llama_token> tokens(text.size() + 8);
    int32_t count = llama_tokenize(
        vocab,
        text.c_str(),
        static_cast<int32_t>(text.size()),
        tokens.data(),
        static_cast<int32_t>(tokens.size()),
        add_special,
        true
    );
    if (count < 0) {
        tokens.assign(static_cast<size_t>(-count), 0);
        count = llama_tokenize(
            vocab,
            text.c_str(),
            static_cast<int32_t>(text.size()),
            tokens.data(),
            static_cast<int32_t>(tokens.size()),
            add_special,
            true
        );
    }
    if (count <= 0) {
        return {};
    }
    tokens.resize(static_cast<size_t>(count));
    return tokens;
}

void decode_single_token(
    llama_context * lctx,
    llama_batch & batch,
    llama_token token,
    llama_pos & n_past,
    bool logits
) {
    batch.n_tokens = 1;
    batch.token[0] = token;
    batch.pos[0] = n_past++;
    batch.n_seq_id[0] = 1;
    batch.seq_id[0][0] = 0;
    batch.logits[0] = logits ? 1 : 0;

    const int32_t decode_result = llama_decode(lctx, batch);
    if (decode_result != 0) {
        std::ostringstream oss;
        oss << "Dekodowanie tokenu nie powiodlo sie, kod: " << decode_result;
        throw std::runtime_error(oss.str());
    }
}

std::string sanitize_ascii_for_jni(const std::string & input) {
    std::string output;
    output.reserve(input.size());
    for (unsigned char ch : input) {
        if (ch == '\n' || ch == '\r' || ch == '\t' || (ch >= 0x20 && ch <= 0x7E)) {
            output.push_back(static_cast<char>(ch));
        } else {
            output.push_back(' ');
        }
    }
    return output;
}

bool is_supported_label_id(const std::string & label_id) {
    if (label_id == "unknown") {
        return true;
    }

    auto has_valid_suffix = [](const std::string & value, size_t prefix_size) {
        if (value.size() != prefix_size + 2) {
            return false;
        }
        const char tens = value[prefix_size];
        const char ones = value[prefix_size + 1];
        if (!std::isdigit(static_cast<unsigned char>(tens)) ||
            !std::isdigit(static_cast<unsigned char>(ones))) {
            return false;
        }
        const int index = (tens - '0') * 10 + (ones - '0');
        return index >= 1 && index <= 20;
    };

    constexpr const char * PLANT_PREFIX = "PLANT_";
    constexpr const char * FUN_PREFIX = "FUN_";
    const std::string plant_prefix(PLANT_PREFIX);
    const std::string fun_prefix(FUN_PREFIX);
    if (label_id.rfind(plant_prefix, 0) == 0) {
        return has_valid_suffix(label_id, plant_prefix.size());
    }
    if (label_id.rfind(fun_prefix, 0) == 0) {
        return has_valid_suffix(label_id, fun_prefix.size());
    }
    return false;
}

std::string extract_prefixed_label_id(
    const std::string & raw_output,
    const std::string & response_prefix
) {
    if (raw_output.rfind(response_prefix, 0) != 0) {
        return "";
    }

    std::string label_id;
    for (size_t i = response_prefix.size(); i < raw_output.size(); ++i) {
        const unsigned char ch = static_cast<unsigned char>(raw_output[i]);
        if (std::isalnum(ch) || ch == '_') {
            label_id.push_back(static_cast<char>(ch));
            continue;
        }
        if (!label_id.empty()) {
            break;
        }
    }
    return label_id;
}

enum llama_flash_attn_type flash_mode_from_native_value(int value) {
    if (value == 0) {
        return LLAMA_FLASH_ATTN_TYPE_DISABLED;
    }
    if (value == 1) {
        return LLAMA_FLASH_ATTN_TYPE_ENABLED;
    }
    return LLAMA_FLASH_ATTN_TYPE_AUTO;
}

std::string flash_mode_name(enum llama_flash_attn_type value) {
    if (value == LLAMA_FLASH_ATTN_TYPE_DISABLED) {
        return "disabled";
    }
    if (value == LLAMA_FLASH_ATTN_TYPE_ENABLED) {
        return "enabled";
    }
    return "auto";
}

std::string json_escape(const std::string & value) {
    std::string out;
    out.reserve(value.size() + 8);
    for (unsigned char ch : value) {
        switch (ch) {
            case '\\':
                out += "\\\\";
                break;
            case '"':
                out += "\\\"";
                break;
            case '\n':
                out += "\\n";
                break;
            case '\r':
                out += "\\r";
                break;
            case '\t':
                out += "\\t";
                break;
            default:
                if (ch >= 0x20 && ch <= 0x7E) {
                    out.push_back(static_cast<char>(ch));
                } else {
                    out.push_back(' ');
                }
                break;
        }
    }
    return out;
}

struct GenerationOptions {
    std::string profile_name = "production";
    int max_new_tokens = 48;
    int gpu_layers = 99;
    bool use_vision_gpu = true;
    enum llama_flash_attn_type flash_attn_type = LLAMA_FLASH_ATTN_TYPE_AUTO;
    int image_min_tokens = IMAGE_MIN_TOKENS;
    int image_max_tokens = IMAGE_MAX_TOKENS;
    bool force_response_prefix = true;
};

struct GenerationOutput {
    std::string profile_name;
    std::string normalized_output;
    std::string raw_output;
    std::string extracted_label_id;
    std::string status;
    std::vector<llama_token> first_token_ids;
    long long model_load_ms = 0;
    long long projector_load_ms = 0;
    long long prefill_ms = 0;
    long long generation_ms = 0;
    long long total_ms = 0;
    int n_past_after_prefill = 0;
};

std::string diagnostic_report_json(
    const GenerationOutput & output,
    const GenerationOptions & options
) {
    std::ostringstream oss;
    oss << "{";
    oss << "\"profile\":\"" << json_escape(output.profile_name) << "\",";
    oss << "\"status\":\"" << json_escape(output.status) << "\",";
    oss << "\"backend\":\"" << (options.gpu_layers > 0 ? "vulkan" : "cpu") << "\",";
    oss << "\"gpu_layers\":" << options.gpu_layers << ",";
    oss << "\"vision_gpu\":" << (options.use_vision_gpu ? "true" : "false") << ",";
    oss << "\"flash_attention\":\"" << flash_mode_name(options.flash_attn_type) << "\",";
    oss << "\"image_min_tokens\":" << options.image_min_tokens << ",";
    oss << "\"image_max_tokens\":" << options.image_max_tokens << ",";
    oss << "\"force_response_prefix\":" << (options.force_response_prefix ? "true" : "false") << ",";
    oss << "\"max_new_tokens\":" << options.max_new_tokens << ",";
    oss << "\"n_past_after_prefill\":" << output.n_past_after_prefill << ",";
    oss << "\"model_load_ms\":" << output.model_load_ms << ",";
    oss << "\"projector_load_ms\":" << output.projector_load_ms << ",";
    oss << "\"prefill_ms\":" << output.prefill_ms << ",";
    oss << "\"generation_ms\":" << output.generation_ms << ",";
    oss << "\"total_ms\":" << output.total_ms << ",";
    oss << "\"first_token_ids\":[";
    for (size_t i = 0; i < output.first_token_ids.size(); ++i) {
        if (i > 0) {
            oss << ",";
        }
        oss << static_cast<int>(output.first_token_ids[i]);
    }
    oss << "],";
    oss << "\"raw_text\":\"" << json_escape(output.raw_output) << "\",";
    oss << "\"extracted_label_id\":\"" << json_escape(output.extracted_label_id) << "\",";
    oss << "\"normalized_text\":\"" << json_escape(output.normalized_output) << "\"";
    oss << "}";
    return oss.str();
}

struct NativeResources {
    llama_model * model = nullptr;
    llama_context * lctx = nullptr;
    mtmd_context * mtmd = nullptr;
    mtmd_bitmap * bitmap = nullptr;
    mtmd_input_chunks * chunks = nullptr;
    llama_sampler * sampler = nullptr;
    llama_batch batch{};
    bool batch_initialized = false;

    ~NativeResources() {
        if (batch_initialized) {
            llama_batch_free(batch);
        }
        if (sampler != nullptr) {
            llama_sampler_free(sampler);
        }
        if (chunks != nullptr) {
            mtmd_input_chunks_free(chunks);
        }
        if (bitmap != nullptr) {
            mtmd_bitmap_free(bitmap);
        }
        if (mtmd != nullptr) {
            mtmd_free(mtmd);
        }
        if (lctx != nullptr) {
            llama_free(lctx);
        }
        if (model != nullptr) {
            llama_model_free(model);
        }
    }
};

GenerationOutput run_generation(
    const std::string & native_library_dir,
    const std::string & language_model_path,
    const std::string & projector_path,
    const std::string & system_prompt,
    const std::string & user_prompt,
    const std::vector<unsigned char> & image_png,
    const GenerationOptions & options
) {
    GenerationOutput result;
    result.profile_name = options.profile_name;
    const auto started_at = std::chrono::steady_clock::now();
    __android_log_print(
        ANDROID_LOG_INFO,
        LOG_TAG,
        "generate start: profile=%s model=%s projector=%s image_bytes=%zu max_new_tokens=%d gpu_layers=%d vision_gpu=%d flash=%s image_tokens=%d-%d",
        options.profile_name.c_str(),
        language_model_path.c_str(),
        projector_path.c_str(),
        image_png.size(),
        options.max_new_tokens,
        options.gpu_layers,
        options.use_vision_gpu ? 1 : 0,
        flash_mode_name(options.flash_attn_type).c_str(),
        options.image_min_tokens,
        options.image_max_tokens
    );

    std::call_once(g_backend_once, [&]() {
        llama_log_set(android_log_callback, nullptr);
        mtmd_helper_log_set(android_log_callback, nullptr);
        ggml_backend_load_all_from_path(native_library_dir.c_str());
        llama_backend_init();
    });
    __android_log_print(ANDROID_LOG_INFO, LOG_TAG, "backend ready at %lld ms", elapsed_ms(started_at));

    NativeResources res;

    llama_model_params model_params = llama_model_default_params();
    model_params.n_gpu_layers = options.gpu_layers;
    model_params.use_mmap = true;
    model_params.check_tensors = false;

    res.model = llama_model_load_from_file(language_model_path.c_str(), model_params);
    if (res.model == nullptr) {
        throw std::runtime_error("Nie udalo sie zaladowac modelu GGUF: " + language_model_path);
    }
    result.model_load_ms = elapsed_ms(started_at);
    __android_log_print(ANDROID_LOG_INFO, LOG_TAG, "model loaded at %lld ms", elapsed_ms(started_at));

    const int threads = native_thread_count();
    llama_context_params ctx_params = llama_context_default_params();
    ctx_params.n_ctx = N_CTX;
    ctx_params.n_batch = N_BATCH;
    ctx_params.n_ubatch = N_UBATCH;
    ctx_params.n_threads = threads;
    ctx_params.n_threads_batch = threads;
    ctx_params.flash_attn_type = options.flash_attn_type;
    ctx_params.no_perf = true;

    res.lctx = llama_init_from_model(res.model, ctx_params);
    if (res.lctx == nullptr) {
        throw std::runtime_error("Nie udalo sie utworzyc kontekstu llama.cpp.");
    }
    __android_log_print(
        ANDROID_LOG_INFO,
        LOG_TAG,
        "context initialized at %lld ms with threads=%d n_ctx=%d",
        elapsed_ms(started_at),
        threads,
        N_CTX
    );

    mtmd_context_params mtmd_params = mtmd_context_params_default();
    mtmd_params.use_gpu = options.use_vision_gpu;
    mtmd_params.n_threads = threads;
    mtmd_params.print_timings = false;
    mtmd_params.warmup = false;
    mtmd_params.flash_attn_type = options.flash_attn_type;
    mtmd_params.image_min_tokens = options.image_min_tokens;
    mtmd_params.image_max_tokens = options.image_max_tokens;

    res.mtmd = mtmd_init_from_file(projector_path.c_str(), res.model, mtmd_params);
    if (res.mtmd == nullptr) {
        throw std::runtime_error("Nie udalo sie zaladowac projektora obrazu: " + projector_path);
    }
    if (!mtmd_support_vision(res.mtmd)) {
        throw std::runtime_error("Zaladowany projektor nie deklaruje wsparcia dla obrazu.");
    }
    result.projector_load_ms = elapsed_ms(started_at);
    __android_log_print(ANDROID_LOG_INFO, LOG_TAG, "projector loaded at %lld ms", elapsed_ms(started_at));

    res.bitmap = mtmd_helper_bitmap_init_from_buf(res.mtmd, image_png.data(), image_png.size());
    if (res.bitmap == nullptr) {
        throw std::runtime_error("Nie udalo sie przetworzyc obrazu dla modelu multimodalnego.");
    }
    __android_log_print(ANDROID_LOG_INFO, LOG_TAG, "bitmap decoded at %lld ms", elapsed_ms(started_at));

    const std::string formatted_prompt = format_chat_prompt(res.model, system_prompt, user_prompt);
    __android_log_print(
        ANDROID_LOG_INFO,
        LOG_TAG,
        "prompt formatted at %lld ms, chars=%zu",
        elapsed_ms(started_at),
        formatted_prompt.size()
    );
    mtmd_input_text text{};
    text.text = formatted_prompt.c_str();
    text.add_special = true;
    text.parse_special = true;

    const mtmd_bitmap * bitmaps[1] = {res.bitmap};
    res.chunks = mtmd_input_chunks_init();
    if (res.chunks == nullptr) {
        throw std::runtime_error("Nie udalo sie utworzyc bufora tokenow multimodalnych.");
    }

    const int32_t tokenize_result = mtmd_tokenize(res.mtmd, res.chunks, &text, bitmaps, 1);
    if (tokenize_result != 0) {
        std::ostringstream oss;
        oss << "Tokenizacja multimodalna nie powiodla sie, kod: " << tokenize_result;
        throw std::runtime_error(oss.str());
    }
    __android_log_print(ANDROID_LOG_INFO, LOG_TAG, "multimodal tokenized at %lld ms", elapsed_ms(started_at));

    llama_pos n_past = 0;
    const auto prefill_started_at = std::chrono::steady_clock::now();
    const int32_t eval_result = mtmd_helper_eval_chunks(
        res.mtmd,
        res.lctx,
        res.chunks,
        n_past,
        0,
        N_BATCH,
        true,
        &n_past
    );
    if (eval_result != 0) {
        std::ostringstream oss;
        oss << "Ewaluacja promptu multimodalnego nie powiodla sie, kod: " << eval_result;
        throw std::runtime_error(oss.str());
    }
    result.prefill_ms = elapsed_ms(prefill_started_at);
    result.n_past_after_prefill = static_cast<int>(n_past);
    __android_log_print(
        ANDROID_LOG_INFO,
        LOG_TAG,
        "prefill evaluated at %lld ms, duration=%lld ms, n_past=%d",
        elapsed_ms(started_at),
        result.prefill_ms,
        static_cast<int>(n_past)
    );

    const llama_vocab * vocab = llama_model_get_vocab(res.model);
    res.sampler = llama_sampler_chain_init(llama_sampler_chain_default_params());
    llama_sampler_chain_add(res.sampler, llama_sampler_init_greedy());
    __android_log_print(
        ANDROID_LOG_INFO,
        LOG_TAG,
        "sampler initialized: greedy"
    );
    res.batch = llama_batch_init(1, 0, 1);
    res.batch_initialized = true;

    const std::string response_prefix = "{\"label_id\":\"";
    if (options.force_response_prefix) {
        const std::vector<llama_token> response_prefix_tokens = tokenize_text(vocab, response_prefix, false);
        if (response_prefix_tokens.empty()) {
            throw std::runtime_error("Nie udalo sie tokenizowac prefiksu odpowiedzi JSON.");
        }
        for (size_t i = 0; i < response_prefix_tokens.size(); ++i) {
            decode_single_token(
                res.lctx,
                res.batch,
                response_prefix_tokens[i],
                n_past,
                i + 1 == response_prefix_tokens.size()
            );
        }
        __android_log_print(
            ANDROID_LOG_INFO,
            LOG_TAG,
            "forced response prefix decoded, tokens=%zu n_past=%d",
            response_prefix_tokens.size(),
            static_cast<int>(n_past)
        );
    }

    std::string output = options.force_response_prefix ? response_prefix : "";
    const int limit = std::max(1, std::min(options.max_new_tokens, 96));
    const auto generation_started_at = std::chrono::steady_clock::now();

    for (int i = 0; i < limit; ++i) {
        const llama_token token = llama_sampler_sample(res.sampler, res.lctx, -1);
        if (llama_vocab_is_eog(vocab, token)) {
            result.status = "eog";
            break;
        }

        const std::string piece = token_to_piece(vocab, token);
        output += piece;
        if (result.first_token_ids.size() < 16) {
            result.first_token_ids.push_back(token);
        }
        const std::string log_piece = sanitize_ascii_for_jni(piece);
        __android_log_print(
            ANDROID_LOG_INFO,
            LOG_TAG,
            "sampled token %d/%d id=%d piece='%s'",
            i + 1,
            limit,
            static_cast<int>(token),
            log_piece.c_str()
        );
        if (options.force_response_prefix &&
            (piece.find('"') != std::string::npos ||
            piece.find('}') != std::string::npos ||
            piece.find('\n') != std::string::npos ||
            piece.find('\r') != std::string::npos)) {
            break;
        }

        decode_single_token(res.lctx, res.batch, token, n_past, true);
        __android_log_print(
            ANDROID_LOG_INFO,
            LOG_TAG,
            "generated token %d/%d at %lld ms",
            i + 1,
            limit,
            elapsed_ms(started_at)
        );
    }

    result.generation_ms = elapsed_ms(generation_started_at);
    result.total_ms = elapsed_ms(started_at);
    if (output.empty()) {
        __android_log_print(ANDROID_LOG_INFO, LOG_TAG, "generate finished empty at %lld ms", elapsed_ms(started_at));
        result.status = "empty";
        result.raw_output = "";
        result.normalized_output = "{\"label_id\":\"unknown\"}";
        return result;
    }
    const std::string sanitized_output = sanitize_ascii_for_jni(output);
    result.raw_output = sanitized_output;
    result.extracted_label_id = options.force_response_prefix
        ? extract_prefixed_label_id(sanitized_output, response_prefix)
        : "";
    if (options.force_response_prefix && !is_supported_label_id(result.extracted_label_id)) {
        __android_log_print(
            ANDROID_LOG_WARN,
            LOG_TAG,
            "generate finished without supported label_id at %lld ms, raw='%s', extracted='%s'",
            elapsed_ms(started_at),
            sanitized_output.c_str(),
            result.extracted_label_id.c_str()
        );
        result.status = "fallback_unknown";
        result.normalized_output = "{\"label_id\":\"unknown\"}";
        return result;
    }
    result.status = result.status.empty() ? "ok" : result.status;
    result.normalized_output = options.force_response_prefix
        ? "{\"label_id\":\"" + result.extracted_label_id + "\"}"
        : sanitized_output;
    __android_log_print(
        ANDROID_LOG_INFO,
        LOG_TAG,
        "generate finished at %lld ms, raw='%s'",
        elapsed_ms(started_at),
        result.normalized_output.c_str()
    );
    return result;
}

GenerationOptions production_options(int max_new_tokens) {
    GenerationOptions options;
    options.max_new_tokens = max_new_tokens;
    return options;
}

std::string generate_impl(
    const std::string & native_library_dir,
    const std::string & language_model_path,
    const std::string & projector_path,
    const std::string & system_prompt,
    const std::string & user_prompt,
    const std::vector<unsigned char> & image_png,
    int max_new_tokens
) {
    return run_generation(
        native_library_dir,
        language_model_path,
        projector_path,
        system_prompt,
        user_prompt,
        image_png,
        production_options(max_new_tokens)
    ).normalized_output;
}

std::string diagnose_impl(
    const std::string & native_library_dir,
    const std::string & language_model_path,
    const std::string & projector_path,
    const std::string & system_prompt,
    const std::string & user_prompt,
    const std::vector<unsigned char> & image_png,
    const GenerationOptions & options
) {
    const GenerationOutput output = run_generation(
        native_library_dir,
        language_model_path,
        projector_path,
        system_prompt,
        user_prompt,
        image_png,
        options
    );
    return diagnostic_report_json(output, options);
}

} // namespace

extern "C"
JNIEXPORT jstring JNICALL
Java_com_naturavision_mobile_inference_JniNativeVisionModelBridge_generateNative(
    JNIEnv * env,
    jobject,
    jstring j_native_library_dir,
    jstring j_language_model_path,
    jstring j_projector_path,
    jstring j_system_prompt,
    jstring j_user_prompt,
    jbyteArray j_image_png,
    jint j_max_new_tokens
) {
    try {
        const std::string result = generate_impl(
            jstring_to_string(env, j_native_library_dir),
            jstring_to_string(env, j_language_model_path),
            jstring_to_string(env, j_projector_path),
            jstring_to_string(env, j_system_prompt),
            jstring_to_string(env, j_user_prompt),
            jbyte_array_to_vector(env, j_image_png),
            static_cast<int>(j_max_new_tokens)
        );
        return env->NewStringUTF(result.c_str());
    } catch (const std::exception & ex) {
        throw_illegal_state(env, ex.what());
        return nullptr;
    }
}

extern "C"
JNIEXPORT jstring JNICALL
Java_com_naturavision_mobile_inference_JniNativeVisionModelBridge_diagnoseNative(
    JNIEnv * env,
    jobject,
    jstring j_native_library_dir,
    jstring j_language_model_path,
    jstring j_projector_path,
    jstring j_system_prompt,
    jstring j_user_prompt,
    jbyteArray j_image_png,
    jstring j_profile_name,
    jint j_max_new_tokens,
    jint j_gpu_layers,
    jboolean j_use_vision_gpu,
    jint j_flash_attention,
    jint j_image_min_tokens,
    jint j_image_max_tokens,
    jboolean j_force_response_prefix
) {
    try {
        GenerationOptions options;
        options.profile_name = jstring_to_string(env, j_profile_name);
        options.max_new_tokens = static_cast<int>(j_max_new_tokens);
        options.gpu_layers = static_cast<int>(j_gpu_layers);
        options.use_vision_gpu = j_use_vision_gpu == JNI_TRUE;
        options.flash_attn_type = flash_mode_from_native_value(static_cast<int>(j_flash_attention));
        options.image_min_tokens = static_cast<int>(j_image_min_tokens);
        options.image_max_tokens = static_cast<int>(j_image_max_tokens);
        options.force_response_prefix = j_force_response_prefix == JNI_TRUE;

        const std::string result = diagnose_impl(
            jstring_to_string(env, j_native_library_dir),
            jstring_to_string(env, j_language_model_path),
            jstring_to_string(env, j_projector_path),
            jstring_to_string(env, j_system_prompt),
            jstring_to_string(env, j_user_prompt),
            jbyte_array_to_vector(env, j_image_png),
            options
        );
        return env->NewStringUTF(result.c_str());
    } catch (const std::exception & ex) {
        throw_illegal_state(env, ex.what());
        return nullptr;
    }
}
