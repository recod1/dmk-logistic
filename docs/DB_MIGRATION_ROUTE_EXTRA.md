# Миграция БД: новые поля таблицы Route

Для поддержки номера для регистрации и номера прицепа в таблицу `Route` нужно добавить два столбца.

## Изменение схемы БД

Выполните в SQLite (или через скрипт миграции):

```sql
ALTER TABLE Route ADD COLUMN registration_number TEXT DEFAULT '';
ALTER TABLE Route ADD COLUMN trailer_number TEXT DEFAULT '';
```

## Проверка

После миграции проверьте структуру таблицы:

```sql
PRAGMA table_info(Route);
```

Должны присутствовать колонки: `registration_number`, `trailer_number`.

## Поведение кода без миграции

Если колонки не добавлены, создание рейсов продолжит работать: репозиторий при ошибке `OperationalError` выполняет вставку без новых полей. При этом поля `registration_number` и `trailer_number` в таких рейсах будут пустыми, а метод `update_route_extra` не будет обновлять их до выполнения миграции.
