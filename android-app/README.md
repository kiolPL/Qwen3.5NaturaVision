# NaturaVision Android

Androidowa aplikacja demonstracyjna pod przyszłe lokalne uruchamianie modelu NaturaVision.

## Co już działa

- wybór zdjęcia z galerii,
- szybkie zdjęcie z aparatu,
- ekran analizy i wyniku,
- warstwa `ForestInferenceEngine`,
- backend demonstracyjny `MockForestInferenceEngine`,
- gotowy punkt podpięcia lokalnego modelu przez `LocalModelRunner`.

## Struktura

- `app/src/main/java/com/naturavision/mobile/ui` - ekran Compose i `ViewModel`
- `app/src/main/java/com/naturavision/mobile/inference` - backendy inferencji i parser odpowiedzi modelu
- `app/src/main/java/com/naturavision/mobile/data` - katalog gatunków
- `app/src/main/java/com/naturavision/mobile/model` - modele domenowe

## Jak podpiąć wytrenowany model

Docelowy punkt integracji to:

- `com.naturavision.mobile.inference.LocalModelRunner`

Obecnie aplikacja używa:

- `MockForestInferenceEngine` dla trybu demo,
- `UnwiredLocalModelRunner` jako placeholder dla lokalnego modelu.

Kiedy finalny model będzie gotowy, należy:

1. dodać bibliotekę lub warstwę JNI do inferencji na urządzeniu,
2. zaimplementować `LocalModelRunner.run(bitmap)`,
3. zwrócić z runnera odpowiedź JSON w formacie:

```json
{
  "label_id": "FUN_01",
  "kingdom": "fungi",
  "scientific_name": "Boletus edulis",
  "polish_name": "borowik szlachetny"
}
```

4. pozostawić parser `ModelOutputParser`, który zamienia ten JSON na obiekt aplikacji.

W aplikacji jest już też gotowy zestaw promptów zgodnych z treningiem:

- `com.naturavision.mobile.inference.PromptTemplates`

Dzięki temu późniejszy runner Android może korzystać z tych samych instrukcji `system` i `user`, które były używane podczas przygotowania danych treningowych.

## Uruchomienie

1. Otwórz folder `android-app` w Android Studio.
2. Poczekaj na synchronizację Gradle.
3. Uruchom moduł `app` na emulatorze lub telefonie.

Jeśli chcesz od razu testować interfejs bez modelu, zostaw wybrany backend `Demo`.
