# Lambda A100 Runbook

Ten runbook przygotowuje bezpieczny trening `Qwen/Qwen3.5-4B` dla projektu NaturaVision na serwerze `Lambda 4x A100 40 GB`.

## Dlaczego ten wariant

- Oficjalny przykład `ms-swift` dla `Qwen3.5-4B` pokazuje fine-tuning z pamięcią treningową `4 x 20 GiB`, `NPROC_PER_NODE=4` i `deepspeed zero2`.
- Lambda publikuje cenę `1.48 USD / GPU / h` dla `A100 40 GB`, czyli około `5.92 USD / h` dla konfiguracji `4x A100 40 GB`.
- To jest najbliższa ścieżka do oficjalnych best practices Qwen/ms-swift, więc daje najwyższą szansę na stabilny run.

Źródła:
- [Qwen3.5 Best Practices](https://swift.readthedocs.io/en/latest/BestPractices/Qwen3_5-Best-Practice.html)
- [Lambda pricing](https://lambda.ai/pricing)
- [Lambda Cloud console](https://docs.lambda.ai/public-cloud/console/)

## 1. Start instancji

W konsoli Lambda wybieram:

- `4x A100 40 GB`
- `Ubuntu 22.04`
- przynajmniej `500 GB` storage
- własny klucz SSH
- region z najszybszym dostępem dla mnie

## 2. Przygotowanie danych lokalnie

Na swoim komputerze buduję przenośny bundle datasetu.

Jeśli pracuję na Windowsie z OneDrive, wybieram katalog poza OneDrive, najlepiej na szybkim dysku lokalnym, na przykład `D:\NaturaVisionPortable`.

```powershell
& ".\.venv-train\Scripts\python.exe" scripts\pack_portable_dataset.py --source-dir data --output-dir D:\NaturaVisionPortable\portable_dataset
```

Tworzę archiwum do wysłania:

```powershell
tar -czf D:\NaturaVisionPortable\portable_dataset.tgz -C D:\NaturaVisionPortable portable_dataset
```

## 3. Wysłanie repo i danych na serwer

Po SSH na serwer klonuję repo i kopiuję archiwum, na przykład przez `scp`:

```bash
scp D:/NaturaVisionPortable/portable_dataset.tgz ubuntu@<lambda-host>:~/
scp -r . ubuntu@<lambda-host>:~/Project-NaturaVision
```

Na serwerze:

```bash
cd ~/Project-NaturaVision
tar -xzf ~/portable_dataset.tgz -C ~
```

Zakładam, że bundle rozpakował się do:

```bash
~/portable_dataset
```

## 4. Bootstrap środowiska na Lambda

```bash
cd ~/Project-NaturaVision
bash train/bootstrap_lambda.sh
source .venv-train-linux/bin/activate
```

Szybki preflight:

```bash
nvidia-smi
swift sft -h
python - <<'PY'
import torch
print(torch.__version__)
print(torch.cuda.is_available())
print(torch.cuda.get_device_name(0))
PY
```

## 5. Przepisanie ścieżek obrazów na Linux

Bundle ma względne ścieżki, więc przepinam je na absolutną ścieżkę Linux:

```bash
cd ~/Project-NaturaVision
source .venv-train-linux/bin/activate
python scripts/rewrite_qwen_image_paths.py \
  --dataset-dir ~/portable_dataset \
  --image-root /home/ubuntu/portable_dataset/images
```

## 6. Smoke test przed pełnym runem

Tworzę mały subset:

```bash
cd ~/Project-NaturaVision
source .venv-train-linux/bin/activate
python scripts/make_smoke_subset.py \
  --source-dir ~/portable_dataset \
  --output-dir ~/portable_dataset_smoke
```

Uruchamiam krótki test end-to-end:

```bash
cd ~/Project-NaturaVision
source .venv-train-linux/bin/activate
DATA_DIR=/home/ubuntu/portable_dataset_smoke \
OUTPUT_ROOT=/home/ubuntu/runs-smoke-lambda \
bash train/train_qwen35_4b_smoke_lambda.sh
```

Jeśli smoke test kończy oba etapy i zapisuje checkpointy, przechodzę do pełnego runu.

## 7. Pełny trening

```bash
cd ~/Project-NaturaVision
source .venv-train-linux/bin/activate
DATA_DIR=/home/ubuntu/portable_dataset \
OUTPUT_ROOT=/home/ubuntu/runs-lambda \
bash train/train_qwen35_4b_lora_lambda.sh
```

Domyślnie skrypt:

- uruchamia `Stage 1` jako `aligner-only`
- uruchamia `Stage 2` jako `llm + aligner`
- używa `NPROC_PER_NODE=4`
- używa `deepspeed zero2`
- ustawia konserwatywny batch pod stabilny run

## 8. Co zapisuję do CV / portfolio

Po runie warto zachować:

- końcowy checkpoint `Stage 2`
- logi z obu etapów
- użyty dataset bundle
- użyty runbook
- finalne metryki walidacyjne
- informację, że trening był robiony na `Lambda 4x A100 40 GB`

## 9. Budżet

Realistyczny budżet dla jednego porządnego przebiegu:

- smoke test: około `0.5-1.0 h`
- pełny run: około `4-8 h`
- razem: około `4.5-9 h`

Przy `5.92 USD / h` daje to mniej więcej:

- `26.64-53.28 USD`

Z bezpiecznym zapasem na jeden dodatkowy rerun:

- planuję budżet `60-90 USD`
