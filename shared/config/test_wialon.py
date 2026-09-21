import requests
import json
from typing import Optional, Dict, List
import sys
from datetime import datetime
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder
import time

class WialonTracker:
    def __init__(self, base_url: str = "https://monitor.sputnik.vision"):
        self.base_url = base_url
        self.sid = None
        self.units_cache = {}
        self.tf = TimezoneFinder()  # для определения часового пояса
        
    def login(self) -> bool:
        """Авторизация в Wialon"""
        print("\n🔐 Авторизация в Wialon...")
        
        params = {
            'svc': 'token/login',
            'params': json.dumps({
                'token': "0000000000000000000000000"
            })
        }
        
        try:
            response = requests.get(f"{self.base_url}/wialon/ajax.html", params=params)
            data = response.json()
            
            if 'eid' in data:
                self.sid = data['eid']
                print("✅ Авторизация успешна!")
                return True
            else:
                print(f"❌ Ошибка авторизации: {data.get('error', 'Неизвестная ошибка')}")
                
        except Exception as e:
            print(f"❌ Ошибка: {e}")
        
        return False
    
    def get_timezone_from_coords(self, lat: float, lng: float) -> str:
        """Определяет часовой пояс по координатам"""
        try:
            timezone_str = self.tf.timezone_at(lng=lng, lat=lat)
            if timezone_str:
                return timezone_str
            else:
                return "Не удалось определить"
        except Exception as e:
            return f"Ошибка: {e}"
    
    def get_all_units(self) -> List[Dict]:
        """Получить список всех машин"""
        print("\n📋 Получение списка всех машин...")
        
        if not self.sid:
            print("❌ Нет активной сессии")
            return []
        
        # Добавляем флаг 0x00002000 (8192) для получения счетчиков (одометра)
        # 1 (базовые) + 256 (доп.свойства) + 1024 (позиция) + 2048 (водитель) + 4096 (датчики) + 8192 (счетчики)
        flags = 1 | 256 | 1024 | 2048 | 4096 | 8192
        
        params = {
            'svc': 'core/search_items',
            'params': json.dumps({
                'spec': {
                    'itemsType': 'avl_unit',
                    'propName': 'sys_name',
                    'propValueMask': '*',
                    'sortType': 'sys_name'
                },
                'force': 1,
                'flags': flags,
                'from': 0,
                'to': 1000
            }),
            'sid': self.sid
        }
        
        try:
            print(f"📡 Отправка запроса с флагом {flags}...")
            response = requests.get(f"{self.base_url}/wialon/ajax.html", params=params)
            data = response.json()
            
            if 'error' in data:
                print(f"❌ Ошибка: {data['error']}")
                return []
            
            if 'items' in data:
                items = data['items']
                print(f"✅ Найдено машин: {len(items)}")
                
                # Сохраняем в кэш
                for unit in items:
                    self.units_cache[unit['id']] = unit
                
                return items
            else:
                print(f"❌ Неожиданный ответ: {data}")
                
        except Exception as e:
            print(f"❌ Ошибка: {e}")
        
        return []
    
    def get_unit_by_id(self, unit_id: int) -> Optional[Dict]:
        """Получить информацию о машине по ID"""
        print(f"\n🔍 Поиск машины по ID: {unit_id}")
        
        flags = 1 | 256 | 1024 | 2048 | 4096 | 8192  # включаем счетчики
        
        params = {
            'svc': 'core/search_item',
            'params': json.dumps({
                'id': unit_id,
                'flags': flags,
                'force': 1
            }),
            'sid': self.sid
        }
        
        try:
            response = requests.get(f"{self.base_url}/wialon/ajax.html", params=params)
            data = response.json()
            
            if 'error' in data:
                print(f"❌ Ошибка: {data['error']}")
                return None
            
            if 'item' in data:
                print(f"✅ Машина найдена!")
                return data['item']
            else:
                print("❌ Машина не найдена")
                
        except Exception as e:
            print(f"❌ Ошибка: {e}")
        
        return None
    
    def search_units_by_name(self, search_term: str) -> List[Dict]:
        """Поиск машин по названию"""
        print(f"\n🔍 Поиск машин по названию: '{search_term}'")
        
        flags = 1 | 256 | 1024 | 2048 | 4096 | 8192  # включаем счетчики
        
        params = {
            'svc': 'core/search_items',
            'params': json.dumps({
                'spec': {
                    'itemsType': 'avl_unit',
                    'propName': 'sys_name',
                    'propValueMask': f'*{search_term}*',
                    'sortType': 'sys_name'
                },
                'force': 1,
                'flags': flags,
                'from': 0,
                'to': 100
            }),
            'sid': self.sid
        }
        
        try:
            response = requests.get(f"{self.base_url}/wialon/ajax.html", params=params)
            data = response.json()
            
            if 'error' in data:
                print(f"❌ Ошибка: {data['error']}")
                return []
            
            if 'items' in data:
                items = data['items']
                print(f"✅ Найдено машин: {len(items)}")
                return items
                
        except Exception as e:
            print(f"❌ Ошибка: {e}")
        
        return []
    
    def format_odometer(self, unit: Dict) -> str:
        """
        Форматирует значение одометра (пробега) из данных счетчиков
        Возвращает пробег с точностью до километра
        """
        try:
            # Пробег хранится в поле 'cnm' (counter mileage)
            if 'cnm' in unit:
                mileage = unit['cnm']
                # Проверяем, что значение целое или с плавающей точкой
                if isinstance(mileage, (int, float)):
                    # Округляем до целого числа километров
                    mileage_int = int(round(mileage))
                    # Форматируем с пробелами для тысяч
                    if mileage_int >= 1000:
                        # Добавляем пробелы между тысячами
                        mileage_str = f"{mileage_int:,}".replace(",", " ")
                        return f"{mileage_str} км"
                    else:
                        return f"{mileage_int} км"
                else:
                    return str(mileage)
            
            # Если структура другая, пробуем найти в 'prp' (properties)
            if 'prp' in unit and isinstance(unit['prp'], dict):
                if 'odometer' in unit['prp']:
                    val = unit['prp']['odometer']
                    if isinstance(val, (int, float)):
                        return f"{int(round(val))} км"
                    return f"{val} км"
                if 'mileage' in unit['prp']:
                    val = unit['prp']['mileage']
                    if isinstance(val, (int, float)):
                        return f"{int(round(val))} км"
                    return f"{val} км"
            
            # Проверяем наличие вложенных счетчиков в 'cnt'
            if 'cnt' in unit and isinstance(unit['cnt'], dict):
                for key, value in unit['cnt'].items():
                    if 'mileage' in key.lower() or 'odometer' in key.lower():
                        if isinstance(value, (int, float)):
                            return f"{int(round(value))} км"
                        return f"{value} км"
            
            return "нет данных"
        except Exception as e:
            return f"ошибка"
    
    def display_units(self, units: List[Dict]):
        """Отображение списка машин с пробегом"""
        if not units:
            print("Нет машин для отображения")
            return
        
        # Увеличиваем ширину таблицы для колонки с пробегом
        print("\n" + "="*180)
        print(f"{'№':<4} {'ID':<12} {'Название':<35} {'Статус':<15} {'Координаты':<35} {'Скорость':<10} {'Пробег (км)':<20} {'Время':<10} {'Часовой пояс':<20}")
        print("="*180)
        
        for i, unit in enumerate(units, 1):
            unit_id = unit.get('id', 'Н/Д')
            name = unit.get('nm', 'Без имени')[:35]
            
            status = "🔴 Нет данных"
            coords = "нет данных"
            speed = "-"
            time_str = ""
            timezone = ""
            
            # Получаем пробег
            odometer = self.format_odometer(unit)
            
            # Обработка позиции
            pos = unit.get('pos')
            if pos and isinstance(pos, dict):
                lat = pos.get('y', 0)
                lng = pos.get('x', 0)
                speed_val = pos.get('s', 0)
                
                if speed_val > 0:
                    status = f"🚗 В движении"
                else:
                    status = "⏹️ На месте"
                
                coords = f"{lat:.6f}, {lng:.6f}"
                speed = f"{speed_val} км/ч"
                
                if 't' in pos:
                    try:
                        dt = datetime.fromtimestamp(pos['t'])
                        time_str = dt.strftime('%H:%M:%S')
                    except:
                        time_str = str(pos['t'])
                
                if lat != 0 and lng != 0:
                    timezone = self.get_timezone_from_coords(lat, lng)
                else:
                    timezone = "координаты = 0"
            else:
                status = "📡 Нет сигнала"
            
            print(f"{i:<4} {unit_id:<12} {name:<35} {status:<15} {coords:<35} {speed:<10} {odometer:<20} {time_str:<10} {timezone:<20}")
        
        print("="*180)
        
        # Статистика
        total = len(units)
        with_pos = sum(1 for u in units if u.get('pos') and isinstance(u.get('pos'), dict))
        with_odometer = sum(1 for u in units if 'cnm' in u or ('prp' in u and ('odometer' in u['prp'] or 'mileage' in u['prp'])))
        moving = sum(1 for u in units if u.get('pos') and isinstance(u.get('pos'), dict) and u['pos'].get('s', 0) > 0)
        
        print(f"\n📊 Статистика:")
        print(f"   Всего машин: {total}")
        print(f"   📍 С координатами: {with_pos}")
        print(f"   📏 С данными пробега: {with_odometer}")
        print(f"   🚗 В движении: {moving}")
        print(f"   ⏹️ На месте: {with_pos - moving}")
    
    def display_unit_details(self, unit: Dict):
        """Детальный вывод информации о машине с пробегом"""
        if not unit:
            return
        
        print("\n" + "="*70)
        print(f"📋 ДЕТАЛЬНАЯ ИНФОРМАЦИЯ О МАШИНЕ")
        print("="*70)
        
        # Основная информация
        print(f"🆔 ID: {unit.get('id', 'Н/Д')}")
        print(f"📝 Название: {unit.get('nm', 'Н/Д')}")
        
        # Информация о пробеге - с точностью до километра
        print(f"\n📏 ПРОБЕГ (ОДОМЕТР):")
        if 'cnm' in unit:
            mileage = unit['cnm']
            mileage_int = int(round(mileage))
            if mileage_int >= 1000:
                mileage_str = f"{mileage_int:,}".replace(",", " ")
                print(f"   Общий пробег: {mileage_str} км")
            else:
                print(f"   Общий пробег: {mileage_int} км")
        else:
            print(f"   Общий пробег: нет данных")
        
        # Дополнительные счетчики
        if 'cfl' in unit:
            print(f"\n🔢 СЧЕТЧИКИ:")
            print(f"   Флаги расчета: {unit['cfl']}")
        if 'cneh' in unit:
            hours = unit['cneh']
            if isinstance(hours, (int, float)):
                hours_int = int(round(hours))
                print(f"   Моточасы: {hours_int} ч")
            else:
                print(f"   Моточасы: {hours} ч")
        if 'cnkb' in unit:
            traffic = unit['cnkb']
            if isinstance(traffic, (int, float)):
                if traffic > 1024:
                    print(f"   GPRS трафик: {traffic/1024:.1f} МБ")
                else:
                    print(f"   GPRS трафик: {traffic} КБ")
            else:
                print(f"   GPRS трафик: {traffic}")
        
        # Координаты и часовой пояс
        pos = unit.get('pos')
        if pos and isinstance(pos, dict):
            lat = pos.get('y', 0)
            lng = pos.get('x', 0)
            speed = pos.get('s', 0)
            
            print(f"\n📍 ТЕКУЩАЯ ПОЗИЦИЯ:")
            print(f"   Широта: {lat:.6f}")
            print(f"   Долгота: {lng:.6f}")
            print(f"   Скорость: {speed} км/ч")
            print(f"   Курс: {pos.get('c', 0)}°")
            print(f"   Высота: {pos.get('z', 0)} м")
            
            if 't' in pos:
                try:
                    dt = datetime.fromtimestamp(pos['t'])
                    print(f"   Время: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
                except:
                    print(f"   Время (timestamp): {pos['t']}")
            
            if lat != 0 and lng != 0:
                timezone = self.get_timezone_from_coords(lat, lng)
                print(f"\n🌍 ЧАСОВОЙ ПОЯС:")
                print(f"   {timezone}")
                
                try:
                    import pytz
                    tz = pytz.timezone(timezone)
                    offset = tz.utcoffset(datetime.now()).total_seconds() / 3600
                    sign = '+' if offset >= 0 else ''
                    print(f"   UTC{sign}{offset:.1f}")
                except:
                    pass
        else:
            print("\n❌ Нет данных о позиции")
        
        print("="*70)

def print_menu():
    print("\n" + "="*60)
    print("🚛 WIALON ТРЕКЕР - С ПРОБЕГОМ (ТОЧНО ДО КМ)")
    print("="*60)
    print("1. 📋 Показать все машины (с пробегом)")
    print("2. 🔍 Найти машину по названию")
    print("3. 🔢 Найти машину по ID")
    print("4. 🚗 Показать движущиеся машины")
    print("5. ⏹️ Показать стоящие машины")
    print("6. 🔄 Обновить список")
    print("0. ❌ Выход")
    print("="*60)

def main():
    # Проверка наличия необходимых библиотек
    try:
        import pytz
    except ImportError:
        print("📦 Устанавливаем pytz...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pytz"])
        import pytz
    
    tracker = WialonTracker()
    
    # Авторизация
    if not tracker.login():
        print("❌ Не удалось авторизоваться")
        return
    
    print("\n✅ Авторизация успешна! Получаем список машин...")
    
    # Получаем список машин
    units = tracker.get_all_units()
    
    if not units:
        print("❌ Не удалось получить список машин")
        return
    
    print(f"\n✅ В системе найдено машин: {len(units)}")
    
    while True:
        print_menu()
        
        choice = input("\nВыберите действие (0-6): ").strip()
        
        if choice == '0':
            print("\n👋 До свидания!")
            break
        
        elif choice == '1':
            tracker.display_units(units)
        
        elif choice == '2':
            search = input("Введите название машины: ").strip()
            if search:
                found = tracker.search_units_by_name(search)
                if found:
                    tracker.display_units(found)
                    
                    if len(found) == 1:
                        show_details = input("\nПоказать детальную информацию с пробегом? (д/н): ").strip().lower()
                        if show_details in ['д', 'да', 'y', 'yes']:
                            tracker.display_unit_details(found[0])
                else:
                    print("Машины не найдены")
        
        elif choice == '3':
            try:
                unit_id = int(input("Введите ID машины: ").strip())
                unit = tracker.get_unit_by_id(unit_id)
                if unit:
                    tracker.display_unit_details(unit)
                else:
                    print("Машина не найдена")
            except ValueError:
                print("❌ Введите корректный ID")
        
        elif choice == '4':
            moving = [u for u in units if u.get('pos') and isinstance(u.get('pos'), dict) and u['pos'].get('s', 0) > 0]
            if moving:
                print(f"\n🚗 ДВИЖУЩИЕСЯ МАШИНЫ: {len(moving)}")
                tracker.display_units(moving)
            else:
                print("Нет движущихся машин")
        
        elif choice == '5':
            stopped = [u for u in units if u.get('pos') and isinstance(u.get('pos'), dict) and u['pos'].get('s', 0) == 0]
            no_pos = [u for u in units if not u.get('pos') or not isinstance(u.get('pos'), dict)]
            
            if stopped:
                print(f"\n⏹️ СТОЯЩИЕ МАШИНЫ: {len(stopped)}")
                tracker.display_units(stopped)
            
            if no_pos:
                print(f"\n❓ МАШИН БЕЗ КООРДИНАТ: {len(no_pos)}")
                tracker.display_units(no_pos)
        
        elif choice == '6':
            units = tracker.get_all_units()
        
        else:
            print("❌ Неверный выбор")
        
        input("\nНажмите Enter для продолжения...")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Программа прервана")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()