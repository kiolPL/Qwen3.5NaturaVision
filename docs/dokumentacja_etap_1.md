# Określenie Tematu I Celu Projektu, Analiza Wymagan

## 1. Temat projektu

Tematem mojego projektu jest przygotowanie lokalnego modelu wizyjnego opartego na rodzinie Qwen3.5, ktory rozpoznaje wybrane rośliny i grzyby spotykane w polskich oraz srodkowoeuropejskich lasach. Model ma dzialac offline na urzadzeniu mobilnym Samsung Galaxy S23 Ultra, dlatego od poczatku zalozylem polaczenie dobrej jakosci rozpoznawania z ograniczonym rozmiarem modelu.

## 2. Cel projektu

Celem mojego projektu jest stworzenie niewielkiego modelu multimodalnego, ktory po otrzymaniu zdjecia potrafi przypisac obiekt do jednej z ustalonych klas roslin lub grzybow lesnych albo zwrocic odpowiedz `unknown`, gdy obraz nie pasuje do obslugiwanej taksonomii lub jest zbyt niejednoznaczny. Chce osiagnac ten cel przez fine-tuning modelu `Qwen/Qwen3.5-4B` na odpowiednio przygotowanym publicznym zbiorze obrazow pochodzacym z iNaturalist.

Efektem praktycznym ma byc model, ktory mozna uruchomic lokalnie na smartfonie bez stalego polaczenia z internetem. Dzieki temu rozwiazanie moze sluzyc jako lekka pomoc edukacyjna do wstepnej identyfikacji gatunkow podczas pobytu w lesie.

## 3. Problem do rozwiazania

Problem, ktory rozwiazuje, polega na tym, ze ogolne modele wizji komputerowej nie sa dostosowane do waskiego zestawu polskich gatunkow lesnych, a jednoczesnie duze modele multimodalne czesto sa zbyt ciezkie, aby uruchomic je lokalnie na telefonie. W praktyce oznacza to konflikt miedzy jakoscia rozpoznawania a ograniczeniami sprzetowymi urzadzenia mobilnego.

W moim projekcie chce rozwiazac ten problem przez:

- ograniczenie zadania do 40 czesto spotykanych taksonow,
- dodanie kontrolowanej klasy `unknown`,
- przygotowanie dobrze przefiltrowanego zbioru danych z Europy z priorytetem dla Polski,
- zastosowanie fine-tuningu LoRA zamiast pelnego trenowania modelu od zera,
- eksport modelu do kwantyzowanego formatu GGUF, ktory nadaje sie do uruchamiania lokalnego.

## 4. Zakres projektu

W ramach projektu realizuje nastepujacy zakres:

- wybieram bazowy model `Qwen/Qwen3.5-4B` jako glowny wariant do strojenia,
- przewiduje docelowe kwantyzacje `Q4_K_M` oraz `Q5_K_M`,
- przygotowuje wariant zapasowy oparty na `Qwen/Qwen3.5-2B`, gdyby docelowe ograniczenia RAM okazaly sie zbyt restrykcyjne,
- buduje pipeline do pobierania i filtrowania danych z iNaturalist,
- przygotowuje manifest 40 klas: 20 roslin i 20 grzybow,
- dziele dane na zbiory treningowe, walidacyjne i testowe,
- konwertuje dane do formatu zgodnego z `ms-swift`,
- przygotowuje skrypt fine-tuningu i eksportu modelu do GGUF,
- definiuje testy sprawdzajace poprawnosc danych i jakosc wynikow.

Poza zakresem projektu znajduje sie:

- rozpoznawanie wszystkich gatunkow roslin i grzybow wystepujacych w Europie,
- diagnoza biologiczna o charakterze eksperckim,
- wdrozenie chmurowe lub serwerowe jako glowny sposob korzystania z modelu,
- automatyczne podejmowanie decyzji wysokiego ryzyka, na przyklad dotyczacych jadalnosci grzybow.

## 5. Wymagane zasoby do wdrozenia modelu

Do realizacji projektu potrzebuje kilku grup zasobow.

### 5.1. Zasoby danych

Jako glowny zbior danych wykorzystuje publiczne obrazy licencjonowane z iNaturalist. Ten wybor jest uzasadniony tym, ze baza udostepnia jednoczesnie obrazy, metadane taksonomiczne, informacje o autorach i licencjach, co pozwala mi przygotowac legalny oraz dobrze opisany zbior treningowy.

Potrzebuje:

- metadanych obserwacji, taksonow i zdjec,
- obrazow przedstawiajacych wybrane gatunki roslin i grzybow,
- metadanych licencyjnych do zachowania atrybucji,
- przykladow negatywnych do klasy `unknown`.

### 5.2. Zasoby sprzetowe

Do treningu wykorzystam moj komputer wyposazony w karte graficzna NVIDIA GeForce RTX 4070. Taki sprzet daje mi mozliwosc przygotowania danych, przeprowadzenia fine-tuningu LoRA oraz wykonania podstawowej walidacji modelu bez potrzeby korzystania z zewnetrznego serwera. Jednoczesnie zakladam, ze trening bedzie realizowany z uzyciem GPU obslugujacego obliczenia w `bfloat16`, poniewaz sam telefon nie nadaje sie do fine-tuningu modelu tej klasy. Telefon Samsung Galaxy S23 Ultra traktuje jako urzadzenie docelowe do inferencji, czyli do uruchamiania juz gotowego i skwantyzowanego modelu.

### 5.3. Zasoby programowe

Do przygotowania projektu wykorzystuje:

- Python do obrobki danych,
- `ms-swift` do fine-tuningu modelu Qwen3.5,
- `llama.cpp` do konwersji i kwantyzacji do GGUF,
- skrypty w Bash do automatyzacji treningu i eksportu,
- biblioteki do walidacji danych i budowy podzbioru z iNaturalist.

## 6. Analiza wymagan

### 6.1. Wymagania funkcjonalne

Moj system powinien spelniac nastepujace wymagania funkcjonalne:

- przyjmowac pojedyncze zdjecie jako dane wejsciowe,
- klasyfikowac obraz do jednej z 40 zdefiniowanych klas albo do klasy `unknown`,
- zwracac wynik w ustalonym formacie JSON,
- dzialac lokalnie bez koniecznosci wysylania zdjec do chmury,
- obslugiwac tylko jeden obraz w jednym zapytaniu,
- zachowywac zgodnosc z przygotowana taksonomia zapisana w manifeście gatunkow.

### 6.2. Wymagania wydajnosciowe

Poniewaz projekt jest kierowany na urzadzenie mobilne, wydajnosc jest jednym z kluczowych wymagan. Zakladam, ze:

- model po kwantyzacji musi miescic sie w praktycznych ograniczeniach pamieci telefonu,
- inferencja musi byc na tyle lekka, aby pojedyncza odpowiedz byla mozliwa do uzyskania lokalnie w akceptowalnym czasie,
- liczba tokenow wyjsciowych powinna byc ograniczona, dlatego wynik ma byc krotkim JSON-em,
- model nie powinien generowac dlugich uzasadnien ani dodatkowego tekstu.

### 6.3. Wymagania jakosciowe

Zalezy mi nie tylko na uruchomieniu modelu, ale tez na jego sensownej jakosci. Dlatego przyjmuje, ze:

- model powinien osiagac dobre wyniki dla 40 znanych klas,
- model powinien umiec odmawiac odpowiedzi poprzez `unknown`, zamiast zgadywac,
- walidacja powinna obejmowac makro-F1 oraz skutecznosc klasy `unknown`,
- szczegolna uwage trzeba zwrocic na gatunki podobne wizualnie, na przyklad brzozy, borowiki i muchomory.

### 6.4. Wymagania skalowalnosci

Skalowalnosc w moim projekcie nie dotyczy glownie ruchu sieciowego, tylko mozliwosci dalszej rozbudowy rozwiazania. Oznacza to, ze:

- pipeline danych powinien umozliwiac dodawanie kolejnych gatunkow,
- skrypty powinny pozwalac na ponowne wygenerowanie zbioru danych i splitow,
- ten sam proces treningowy powinien dawac sie uruchomic dla modelu 4B i wariantu 2B,
- struktura projektu powinna byc na tyle uporzadkowana, aby mozna bylo pozniej dolaczyc nowe benchmarki i nowe wersje modeli.

### 6.5. Wymagania bezpieczenstwa i prywatnosci

Bezpieczenstwo w tym projekcie rozumiem przede wszystkim jako bezpieczenstwo danych oraz odpowiedzialne uzycie modelu. Z tego powodu:

- stawiam na lokalne uruchamianie modelu, aby ograniczyc przesylanie danych uzytkownika,
- korzystam z publicznych danych o jasno okreslonych licencjach,
- zachowuje informacje o autorach i licencjach zdjec,
- nie traktuje wyniku modelu jako porady eksperckiej, zwlaszcza przy grzybach jadalnych i trujacych,
- zakres zastosowania ograniczam do zadania edukacyjno-demonstracyjnego.

## 7. Uzasadnienie wyboru modelu

Za najlepsza baze do tego projektu uznalem `Qwen/Qwen3.5-4B`. Ten model jest kompromisem miedzy jakoscia a rozmiarem. Wariant 4B jest wyraznie mniejszy od 9B, ale nadal zachowuje wysoki poziom jakosci w zadaniach multimodalnych. Jednoczesnie po kwantyzacji do `Q4_K_M` lub `Q5_K_M` daje realna szanse uruchomienia na telefonie klasy Samsung Galaxy S23 Ultra.

Nie wybralem wiekszego modelu, poniewaz zalezy mi na uruchamianiu lokalnym. Nie wybralem tez jako glownego wariantu modelu 2B, poniewaz chcialem zachowac lepsza jakosc rozpoznawania. Wariant 2B traktuje jako plan awaryjny, jezeli testy na rzeczywistym urzadzeniu pokaza zbyt duze zuzycie pamieci.

## 8. Oczekiwany wynik

Oczekiwanym wynikiem mojego projektu jest jasno zdefiniowany i udokumentowany system do budowy lokalnego modelu rozpoznajacego wybrane rośliny i grzyby lesne. Na poziomie technicznym rezultatem ma byc:

- przygotowany zbior danych oparty na iNaturalist,
- komplet skryptow do filtrowania danych, tworzenia splitow i walidacji,
- skrypt fine-tuningu modelu `Qwen/Qwen3.5-4B`,
- eksport gotowego modelu do formatu GGUF w wersjach skwantyzowanych,
- dokumentacja wymagan i zalozen projektu.

Na poziomie merytorycznym oczekuje, ze bede mial jasno okreslony cel projektu, zamkniety zakres, zestaw wymaganych zasobow oraz mierzalne wymagania dotyczace jakosci, wydajnosci, skalowalnosci i bezpieczenstwa.

## 9. Podsumowanie

W tym projekcie rozwijam lokalny system do identyfikacji 40 czesto spotykanych gatunkow roslin i grzybow lesnych. Moj glowny cel polega na polaczeniu praktycznej uzytecznosci z ograniczeniami mobilnymi, dlatego caly projekt buduje wokol niewielkiego modelu Qwen3.5, starannie dobranych danych i kontrolowanego procesu fine-tuningu. Uwazam, ze takie podejscie dobrze odpowiada wymaganiom zadania, poniewaz prowadzi jednoczesnie do jasno okreslonego celu projektu i do kompletnej dokumentacji wymagan.

## 10. Lista klas w projekcie

W moim projekcie model rozpoznaje 40 podstawowych klas gatunkowych. Sa to klasy stale, zapisane w manifeście gatunkow i wykorzystywane podczas przygotowania danych, treningu oraz testowania modelu.

### 10.1. Klasy roslin

- `PLANT_01` - sosna zwyczajna (`Pinus sylvestris`)
- `PLANT_02` - swierk pospolity (`Picea abies`)
- `PLANT_03` - brzoza brodawkowata (`Betula pendula`)
- `PLANT_04` - brzoza omszona (`Betula pubescens`)
- `PLANT_05` - dab szypulkowy (`Quercus robur`)
- `PLANT_06` - dab bezszypulkowy (`Quercus petraea`)
- `PLANT_07` - buk zwyczajny (`Fagus sylvatica`)
- `PLANT_08` - olsza czarna (`Alnus glutinosa`)
- `PLANT_09` - osika (`Populus tremula`)
- `PLANT_10` - klon zwyczajny (`Acer platanoides`)
- `PLANT_11` - jarzab pospolity (`Sorbus aucuparia`)
- `PLANT_12` - leszczyna pospolita (`Corylus avellana`)
- `PLANT_13` - borowka czarna (`Vaccinium myrtillus`)
- `PLANT_14` - borowka brusznica (`Vaccinium vitis-idaea`)
- `PLANT_15` - wrzos zwyczajny (`Calluna vulgaris`)
- `PLANT_16` - konwalia majowa (`Convallaria majalis`)
- `PLANT_17` - szczawik zajeczy (`Oxalis acetosella`)
- `PLANT_18` - zawilec gajowy (`Anemone nemorosa`)
- `PLANT_19` - konwalijka dwulistna (`Maianthemum bifolium`)
- `PLANT_20` - orlica pospolita (`Pteridium aquilinum`)

### 10.2. Klasy grzybow

- `FUN_01` - borowik szlachetny (`Boletus edulis`)
- `FUN_02` - kozlarz babka (`Leccinum scabrum`)
- `FUN_03` - kozlarz czerwony (`Leccinum aurantiacum`)
- `FUN_04` - pieprznik jadalny (`Cantharellus cibarius`)
- `FUN_05` - maslak zwyczajny (`Suillus luteus`)
- `FUN_06` - maslak sitarz (`Suillus bovinus`)
- `FUN_07` - mleczaj rydz (`Lactarius deliciosus`)
- `FUN_08` - mleczaj swierkowy (`Lactarius deterrimus`)
- `FUN_09` - golabek zielonawofioletowy (`Russula cyanoxantha`)
- `FUN_10` - golabek blotny (`Russula claroflava`)
- `FUN_11` - czubajka kania (`Macrolepiota procera`)
- `FUN_12` - muchomor czerwony (`Amanita muscaria`)
- `FUN_13` - muchomor sromotnikowy (`Amanita phalloides`)
- `FUN_14` - opienka miodowa (`Armillaria mellea`)
- `FUN_15` - czernidlak kolpakowaty (`Coprinus comatus`)
- `FUN_16` - purchawka chropowata (`Lycoperdon perlatum`)
- `FUN_17` - sromotnik bezwstydny (`Phallus impudicus`)
- `FUN_18` - pniarek obrzezony (`Fomitopsis pinicola`)
- `FUN_19` - wrosniak roznobarwny (`Trametes versicolor`)
- `FUN_20` - podgrzybek czerwonawy (`Xerocomellus chrysenteron`)

### 10.3. Klasa dodatkowa

Oprocz 40 klas gatunkowych uwzgledniam tez klase logiczna `unknown`. Korzystam z niej wtedy, gdy zdjecie nie przedstawia zadnego z obslugiwanych gatunkow albo gdy obraz jest zbyt niejednoznaczny, aby model mogl udzielic wiarygodnej odpowiedzi.
