# NaturaVision Android

Androidowa aplikacja demonstracyjna dla modelu NaturaVision.

## Co dziala

- wybor zdjecia z galerii,
- szybkie zdjecie z aparatu,
- analiza obrazu przez wybrany backend,
- ekran wyniku z label_id, nazwa polska, nazwa lacinska, nazwa angielska i krolestwem,
- lokalny katalog wszystkich klas modelu: 20 roslin, 20 grzybow i `unknown`,
- parser odpowiedzi modelu w formacie `{"label_id":"..."}`,
- dedykowany przycisk `Uruchom test suite` do testowania modelu na telefonie,
- smoke test backendu, parsera, promptu i katalogu taksonomii.

## Integracja modelu

Punkt integracji modelu znajduje sie tutaj:

```text
app/src/main/java/com/naturavision/mobile/inference/LocalModelRunner.kt
```

Aktualna aplikacja ma gotowa architekture pod lokalny model:

- `JsonForestInferenceEngine` oczekuje odpowiedzi JSON z modelem `label_id`,
- `ModelOutputParser` mapuje `label_id` na informacje o gatunku,
- `TaxonomyCatalog` zawiera wszystkie publiczne klasy,
- `PromptTemplates` zawiera prompt z pelna taksonomia,
- `UnwiredLocalModelRunner` jasno sygnalizuje, ze brakuje jeszcze natywnego runtime GGUF/JNI.

Wazne: paczka `adapter_model.safetensors` z treningu QLoRA nie jest samodzielnym modelem mobilnym. Do inferencji na telefonie potrzebny jest pelny eksport po merge adaptera z modelem bazowym, np.:

```text
files/model/naturavision/forest-taxa-qwen35-4b-q4_k_m.gguf
files/model/naturavision/forest-taxa-qwen35-4b-mmproj.gguf
```

Po dodaniu runtime Android/NDK runner powinien zwracac minimalny JSON:

```json
{"label_id":"FUN_01"}
```

Pelne informacje o gatunku sa uzupelniane po stronie aplikacji.

## Test suite na telefonie

Przycisk `Uruchom test suite` sprawdza:

- kompletnosc katalogu gatunkow,
- unikalnosc `label_id`,
- mapowanie parsera dla wszystkich klas,
- obecnosc klas w prompcie systemowym,
- obecnosc adaptera QLoRA,
- obecnosc pelnego modelu GGUF i projektora obrazu,
- smoke test inferencji demo,
- gotowosc lokalnego runnera modelu.

Do czasu dodania pelnego GGUF i natywnego runnera lokalny model bedzie oznaczony jako `WARN`, a nie jako pelny blad aplikacji.

## Uruchomienie

1. Otworz folder `android-app` w Android Studio.
2. Poczekaj na synchronizacje Gradle.
3. Uruchom modul `app` na emulatorze albo telefonie.
4. Na telefonie wybierz zdjecie i uzyj `Uruchom analize`.
5. Uzyj `Uruchom test suite`, zeby sprawdzic gotowosc modelu i aplikacji.
