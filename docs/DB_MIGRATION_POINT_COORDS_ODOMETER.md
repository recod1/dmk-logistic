# Миграция БД: координаты и одометр для точек

Для фиксации координат ТС и одометра при смене статуса точки.

```sql
ALTER TABLE Point ADD COLUMN lat REAL DEFAULT NULL;
ALTER TABLE Point ADD COLUMN lng REAL DEFAULT NULL;
ALTER TABLE Point ADD COLUMN odometer TEXT DEFAULT NULL;
```

Проверка: `PRAGMA table_info(Point);`
