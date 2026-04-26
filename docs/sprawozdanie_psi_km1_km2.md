# Sprawozdanie Projektowe PSI

## Podpisy

Imię i nazwisko: Mateusz Adamczak

Numer albumu / grupa: 423062, pracuję samodzielnie

Temat projektu: **NaturaVision - lokalny model wizyjny do rozpoznawania roślin i grzybów leśnych**

---

## Kamień Milowy 1

### Temat projektu

Tematem mojego projektu jest przygotowanie lokalnego modelu wizyjnego, który rozpoznaje wybrane rośliny i grzyby spotykane w polskich oraz środkowoeuropejskich lasach. Projekt realizuję w taki sposób, aby końcowy model dało się uruchomić offline na urządzeniu mobilnym, a dokładniej na telefonie Samsung Galaxy S23 Ultra.

Główną ideą projektu jest połączenie dwóch rzeczy: dobrej jakości rozpoznawania obrazu oraz małych wymagań sprzętowych. Nie chciałem budować rozwiązania chmurowego ani dużego modelu, który działa wyłącznie na mocnym serwerze. Zależało mi na tym, aby cały system był praktyczny, lekki i możliwy do użycia lokalnie.

### Cel projektu

Celem mojego projektu jest stworzenie modelu multimodalnego, który po otrzymaniu zdjęcia potrafi wskazać, czy przedstawia ono jeden z wybranych gatunków roślin lub grzybów leśnych, czy też powinien zwrócić odpowiedź `unknown`, gdy obraz nie pasuje do obsługiwanej taksonomii albo jest zbyt niejednoznaczny.

W praktyce moim celem jest:

- przygotowanie własnego, dobrze przefiltrowanego zbioru danych obrazowych,
- dopasowanie modelu wizji komputerowej do konkretnego zadania biologicznego,
- przetestowanie lokalnego fine-tuningu małego modelu multimodalnego,
- przygotowanie rozwiązania, które po zakończeniu projektu będzie można skwantyzować i uruchamiać na telefonie.

### Problem, który rozwiązuję

Problem polega na tym, że ogólne modele rozpoznawania obrazu zwykle nie są dopasowane do wąskiej grupy gatunków występujących w polskich lasach. Z drugiej strony bardzo duże modele multimodalne są zbyt ciężkie, aby uruchamiać je lokalnie na smartfonie. W efekcie trzeba znaleźć kompromis między jakością modelu a jego rozmiarem i kosztami obliczeniowymi.

W moim projekcie rozwiązuję ten problem przez:

- ograniczenie zadania do 40 konkretnych gatunków,
- dodanie kontrolowanej klasy `unknown`,
- użycie publicznych danych z iNaturalist,
- przygotowanie własnego pipeline'u filtrowania i czyszczenia danych,
- wykorzystanie lekkiego fine-tuningu QLoRA zamiast pełnego treningu od zera.

### Co chcę przewidywać

Model ma przewidywać jedną z 41 klas logicznych:

- 20 klas roślin,
- 20 klas grzybów,
- 1 klasę `unknown`.

Przykładowe klasy to:

- `PLANT_01` - sosna zwyczajna,
- `PLANT_03` - brzoza brodawkowata,
- `FUN_01` - borowik szlachetny,
- `FUN_12` - muchomor czerwony,
- `unknown` - obraz spoza taksonomii lub zbyt niejednoznaczny.

### Wybrany zbiór danych

Jako główne źródło danych wybrałem **iNaturalist Open Data**:

- AWS Registry: [iNaturalist Licensed Observation Images](https://registry.opendata.aws/inaturalist-open-data/)
- dokumentacja: [iNaturalist Open Data GitHub](https://github.com/inaturalist/inaturalist-open-data)

Wybrałem ten zbiór, ponieważ:

- zawiera zdjęcia wraz z metadanymi taksonomicznymi,
- pozwala filtrować dane po licencjach,
- zawiera informacje o lokalizacji obserwacji,
- umożliwia zbudowanie własnego, wąskiego podzbioru odpowiadającego tematowi projektu.

### Wybrany model i plan techniczny

Po przeanalizowaniu wariantów rodziny Qwen3.5 wybrałem model `Qwen/Qwen3.5-4B` jako bazę do fine-tuningu. Uznałem, że jest to najlepszy kompromis między jakością rozpoznawania a rozmiarem modelu. Większe warianty byłyby zbyt ciężkie do lokalnego wdrożenia, a mniejsze mogłyby zbyt mocno obniżyć jakość rozpoznawania.

Mój plan techniczny wyglądał następująco:

- przygotowanie danych w formacie zgodnym z `ms-swift`,
- lokalny fine-tuning w trybie `4-bit QLoRA`,
- testy lokalnego uruchamiania na komputerze z GPU RTX 4070,
- późniejsza kwantyzacja modelu do formatu GGUF,
- test uruchomienia na urządzeniu mobilnym.

### Narzędzia i środowisko

W projekcie wykorzystałem:

- Python do obróbki danych i automatyzacji pipeline'u,
- `ms-swift` do fine-tuningu modelu Qwen3.5,
- `WSL2` z Ubuntu jako środowisko treningowe,
- `bitsandbytes` do treningu `4-bit QLoRA`,
- `llama.cpp` jako docelowe narzędzie do późniejszej konwersji i kwantyzacji,
- własne skrypty do budowy datasetu, splitów i walidacji.

Do treningu lokalnego wykorzystuję swój komputer z kartą **NVIDIA GeForce RTX 4070**, a telefon Samsung Galaxy S23 Ultra traktuję jako urządzenie docelowe do inferencji.

### Dokumentacja graficzna do Kamienia Milowego 1

![Screen 1 - struktura projektu](screenshots/km1/scr1.png)

**Rysunek 1.** Struktura projektu obejmująca główne foldery i pliki wykorzystywane do przygotowania danych, dokumentacji oraz treningu modelu.

![Screen 2 - manifest klas](screenshots/km1/scr2.png)

**Rysunek 2.** Fragment pliku `species_manifest.csv` przedstawiający zdefiniowane klasy roślin i grzybów wykorzystywane w projekcie.

---

## Kamień Milowy 2

### Dokładniejszy opis zbioru danych

Po przygotowaniu własnego podzbioru z iNaturalist otrzymałem surowy zbiór `records.csv` zawierający **21193 rekordy obrazowe**. W tej liczbie:

- każda z 40 klas docelowych ma po około `449-450` obrazów,
- klasa `unknown` ma `3199` obrazów,
- `17954` rekordy pochodzą z Polski,
- `3239` rekordów pochodzi z innych krajów europejskich.

Rozkład licencji w surowym zbiorze wygląda następująco:

- `CC0` - `601` rekordów,
- `CC-BY` - `2071` rekordów,
- `CC-BY-NC` - `18521` rekordów.

Na potrzeby treningu przygotowałem finalne splity:

- `train.jsonl` - `14000` rekordów,
- `val.jsonl` - `2400` rekordów,
- `test.jsonl` - `2400` rekordów.

W podziale finalnym:

- każda z 40 klas docelowych ma układ `300 / 50 / 50`,
- klasa `unknown` ma układ `2000 / 400 / 400`.

Oznacza to, że finalnie pracuję na **18800** przykładach przeznaczonych bezpośrednio do treningu, walidacji i testu.

### Obróbka zbioru danych - etap po etapie

Obróbkę danych wykonałem etapami.

#### 1. Zdefiniowanie taksonomii

Najpierw przygotowałem manifest gatunków `species_manifest.csv`, w którym zapisałem:

- identyfikatory klas,
- nazwy łacińskie,
- nazwy polskie,
- podział na rośliny i grzyby.

Dzięki temu od początku miałem ustaloną zamkniętą listę klas, które model ma rozpoznawać.

#### 2. Pobranie i przygotowanie metadanych iNaturalist

Następnie pobrałem metadane iNaturalist i przygotowałem z nich własny podzbiór. W tym etapie korzystałem z:

- `observations.csv.gz`,
- `photos.csv.gz`,
- `taxa.csv.gz`.

#### 3. Filtrowanie obserwacji

Kolejnym krokiem było odfiltrowanie danych według założeń projektu. Zostawiłem tylko rekordy spełniające moje wymagania:

- tylko wybrane gatunki z manifestu oraz dodatkową pulę do klasy `unknown`,
- tylko licencje `CC0`, `CC-BY` i `CC-BY-NC`,
- tylko obserwacje z Europy,
- priorytet dla obserwacji z Polski,
- jedna fotografia na obserwację,
- maksymalnie dwie fotografie od jednego obserwatora.

Ten etap był bardzo ważny, bo właśnie tutaj dopasowałem ogólny publiczny zbiór do bardzo konkretnego tematu projektu.

#### 4. Pobranie obrazów i zapis atrybucji

Po odfiltrowaniu metadanych pobrałem obrazy w rozdzielczości `large` i zapisałem je w uporządkowanej strukturze katalogów. Dodatkowo zapisałem informacje o autorach i licencjach do pliku `attribution.csv`.

#### 5. Podział na train / val / test

Następnie przygotowałem zbalansowane splity:

- zbiór treningowy,
- zbiór walidacyjny,
- zbiór testowy.

Zależało mi na tym, aby klasy docelowe miały równy rozkład, a klasa `unknown` była liczniejsza i rzeczywiście uczyła model odmawiania odpowiedzi zamiast zgadywania.

#### 6. Konwersja do formatu treningowego

Ostatnim krokiem było przekształcenie danych do formatu zgodnego z `ms-swift`. Każdy rekord końcowy zawiera:

- listę wiadomości `system / user / assistant`,
- ścieżkę do obrazu,
- oczekiwaną odpowiedź JSON z etykietą klasy.

### Fragment finalnie obrobionych danych

Przykładowy rekord końcowy w formacie JSONL wygląda następująco:

```json
{
  "messages": [
    {
      "role": "system",
      "content": "You identify one forest organism from a fixed taxonomy and answer in JSON only."
    },
    {
      "role": "user",
      "content": "<image>Identify the organism. If it is not in the supported taxonomy or the image is ambiguous, return unknown."
    },
    {
      "role": "assistant",
      "content": "{\"label_id\":\"FUN_01\",\"kingdom\":\"fungi\",\"scientific_name\":\"Boletus edulis\",\"polish_name\":\"borowik szlachetny\"}"
    }
  ],
  "images": [
    "/home/uzytkownik/naturavision-data/images/FUN_01/123456.jpg"
  ]
}
```

Oprócz tego przygotowałem walidację datasetu, która sprawdzała:

- zgodność etykiet z manifestem,
- istnienie plików obrazów,
- poprawność podziału train / val / test,
- brak przecieków obserwacji między splitami,
- oczekiwane liczności klas.

### Przygotowanie treningu

Po przygotowaniu danych uruchomiłem również część treningową projektu. W tym etapie:

- przygotowałem środowisko WSL2,
- uruchomiłem trening `4-bit QLoRA` dla `Qwen/Qwen3.5-4B`,
- wykonałem smoke run na małym podzbiorze,
- wykonałem canary run na pełnym zbiorze,
- uruchomiłem pełny run w konfiguracji zoptymalizowanej czasowo.

W czasie pracy rozwiązałem kilka problemów technicznych:

- problem z pobieraniem modelu przez `xet`,
- problem z działaniem środowiska WSL2,
- problem z interpretacją `max_steps` po wznowieniu `Stage 2`.

Dzięki temu przygotowałem działający pipeline lokalnego treningu na komputerze z RTX 4070.

### Zmiana pierwotnego planu treningu

Na początku zakładałem, że będę trenował pełną, nieskwantyzowaną wersję modelu `Qwen/Qwen3.5-4B`, a dopiero po zakończeniu treningu wykonam kwantyzację do lżejszej wersji przeznaczonej na telefon. W trakcie pracy zmieniłem jednak ten plan.

Powodem tej zmiany były ograniczenia sprzętowe mojego komputera. Do pełnego treningu modelu tej klasy potrzebne są wyraźnie większe zasoby GPU niż te, którymi dysponuję lokalnie. Mój komputer z kartą NVIDIA GeForce RTX 4070 pozwala na przygotowanie danych, testy oraz uruchomienie lżejszego fine-tuningu, ale nie daje bezpiecznego zapasu pamięci do pełnego treningu gęstej wersji modelu `Qwen3.5-4B`.

Z tego powodu przeszedłem na podejście `4-bit QLoRA`, czyli trening adapterów na skwantyzowanej bazie modelu. Takie rozwiązanie pozwoliło mi:

- uruchomić trening lokalnie bez przekroczenia pamięci GPU,
- zachować model `Qwen/Qwen3.5-4B` jako bazę projektu,
- dalej przygotowywać model pod późniejsze wdrożenie mobilne,
- znacząco obniżyć koszt obliczeniowy eksperymentów i testów.

Oznacza to, że w praktyce zmieniłem strategię z modelu "najpierw pełny trening, potem kwantyzacja" na strategię "trening w trybie skwantyzowanym już na etapie fine-tuningu", ponieważ tylko takie podejście było realistyczne w warunkach sprzętowych, którymi dysponuję.

### Stan obecny projektu

Na moment przygotowania tego sprawozdania:

- pipeline danych jest gotowy,
- zbiór treningowy, walidacyjny i testowy jest gotowy,
- format danych pod `ms-swift` jest gotowy,
- lokalny trening został uruchomiony testowo,
- właściwy długi trening dokończę w następnym etapie pracy.

Uważam, że najważniejszym rezultatem drugiego kamienia milowego jest to, że nie tylko przygotowałem dane, ale też zbudowałem pełny i powtarzalny pipeline od surowych metadanych do gotowego środowiska treningowego.

### Dokumentacja graficzna do Kamienia Milowego 2

![Screen KM2-1 - records.csv](screenshots/km2/scr1.png)

**Rysunek 3.** Fragment pliku `records.csv` po filtrowaniu danych z iNaturalist, zawierający przypisanie klas, identyfikatory obserwacji, informacje licencyjne i linki do obrazów.

![Screen KM2-2 - katalog obrazów](screenshots/km2/scr2.png)

**Rysunek 4.** Struktura katalogu z przygotowanymi obrazami, uporządkowanymi według klas roślin, grzybów oraz klasy `unknown`.

![Screen KM2-3 - train.jsonl](screenshots/km2/scr3.png)

**Rysunek 5.** Fragment pliku `train.jsonl` po konwersji do formatu zgodnego z `ms-swift`, zawierający rekordy treningowe z komunikatami `system`, `user`, `assistant` oraz ścieżką do obrazu.

![Screen KM2-4 - pliki splitów](screenshots/km2/scr4.png)

**Rysunek 6.** Wygenerowane pliki podziału danych na część treningową, walidacyjną i testową po wykonaniu etapu budowy splitów.

![Screen KM2-5 - skrypty projektu](screenshots/km2/scr5.png)

**Rysunek 7.** Fragment struktury skryptów projektu obejmujący pipeline przygotowania danych oraz skrypty uruchamiania treningu modelu.

## Krótkie podsumowanie

W tym etapie projektu przygotowałem kompletny podzbiór danych do rozpoznawania roślin i grzybów leśnych, zbudowałem własny pipeline filtrowania danych z iNaturalist, przygotowałem format treningowy pod `ms-swift` i uruchomiłem lokalne testy treningowe modelu `Qwen/Qwen3.5-4B` w trybie `4-bit QLoRA`. Dzięki temu mam gotową bazę do dalszych eksperymentów oraz do właściwego pełnego treningu modelu.
