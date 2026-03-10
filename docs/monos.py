import requests
import json
from typing import Optional, Dict, List, Any
import sys
from datetime import datetime
from timezonefinder import TimezoneFinder
import time

class WialonTracker:
    def __init__(self, base_url: str = "http://w1.wialon.justgps.ru"):
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
                'token': "1b78c9f1f54d396c5712d7620b06ad61C3C50B6594F0117363B7EA3F9B64F53A1722A315"
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
    
    def extract_temperature_sensors(self, unit: Dict) -> Dict[str, Any]:
        """
        Извлекает данные о температуре из датчиков объекта
        В Wialon датчики температуры относятся к типу "temperature" (аналоговые датчики) [citation:4]
        """
        result = {}
        
        try:
            # Проверяем наличие датчиков в ответе
            # Датчики могут быть в поле 'sens' или 'sensors' [citation:2]
            sensors = unit.get('sens', [])
            if not sensors and 'sensors' in unit:
                sensors = unit.get('sensors', [])
            
            if sensors and isinstance(sensors, list):
                temp_sensors = []
                for sensor in sensors:
                    # Проверяем тип датчика - для температуры это может быть "temperature" [citation:4]
                    sensor_type = sensor.get('t', '').lower() if isinstance(sensor.get('t'), str) else ''
                    sensor_name = sensor.get('n', '').lower() if isinstance(sensor.get('n'), str) else ''
                    
                    # Ищем датчики температуры по названию или типу
                    if ('temp' in sensor_name or 'temperature' in sensor_type or 
                        sensor_type == 'temperature' or 'холод' in sensor_name or 
                        'реф' in sensor_name or 'ref' in sensor_name):
                        
                        # Текущее значение датчика [citation:2]
                        value = sensor.get('v')
                        if value is not None:
                            # Форматируем с одним знаком после запятой
                            try:
                                value_float = float(value)
                                temp_sensors.append({
                                    'name': sensor.get('n', 'Без имени'),
                                    'value': round(value_float, 1),
                                    'unit': '°C'
                                })
                            except (ValueError, TypeError):
                                pass
                
                if temp_sensors:
                    result['temperature_sensors'] = temp_sensors
            
            # Также проверяем поле 'prp' (properties) на наличие температурных параметров
            prp = unit.get('prp', {})
            if prp and isinstance(prp, dict):
                temp_params = {}
                for key, value in prp.items():
                    if 'temp' in key.lower() and isinstance(value, (int, float)):
                        try:
                            temp_params[key] = round(float(value), 1)
                        except:
                            pass
                
                if temp_params:
                    result['temperature_params'] = temp_params
            
            # Проверяем поле 'cnt' (counters) на наличие температурных счетчиков
            cnt = unit.get('cnt', {})
            if cnt and isinstance(cnt, dict):
                temp_counters = {}
                for key, value in cnt.items():
                    if 'temp' in key.lower() and isinstance(value, (int, float)):
                        try:
                            temp_counters[key] = round(float(value), 1)
                        except:
                            pass
                
                if temp_counters:
                    result['temperature_counters'] = temp_counters
                    
        except Exception as e:
            print(f"⚠️ Ошибка при извлечении температуры: {e}")
        
        return result
    
    def get_all_units(self) -> List[Dict]:
        """Получить список всех машин"""
        print("\n📋 Получение списка всех машин...")
        
        if not self.sid:
            print("❌ Нет активной сессии")
            return []
        
        # Добавляем флаги для получения всех данных:
        # 1 (базовые) + 256 (доп.свойства) + 1024 (позиция) + 2048 (водитель) + 
        # 4096 (датчики) + 8192 (счетчики) + 16384 (свойства датчиков)
        flags = 1 | 256 | 1024 | 2048 | 4096 | 8192 | 16384
        
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
        
        flags = 1 | 256 | 1024 | 2048 | 4096 | 8192 | 16384
        
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
        
        flags = 1 | 256 | 1024 | 2048 | 4096 | 8192 | 16384
        
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
        """Форматирует значение одометра с точностью до километра"""
        try:
            if 'cnm' in unit:
                mileage = unit['cnm']
                if isinstance(mileage, (int, float)):
                    mileage_int = int(round(mileage))
                    if mileage_int >= 1000:
                        mileage_str = f"{mileage_int:,}".replace(",", " ")
                        return f"{mileage_str} км"
                    else:
                        return f"{mileage_int} км"
                else:
                    return str(mileage)
            
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
            
            return "нет данных"
        except Exception as e:
            return "ошибка"
    
    def format_temperature(self, unit: Dict) -> str:
        """
        Форматирует данные о температуре для отображения в общем списке
        """
        temp_data = self.extract_temperature_sensors(unit)
        
        if not temp_data:
            return "нет данных"
        
        # Собираем все значения температуры в одну строку
        temp_strings = []
        
        # Основные датчики температуры
        if 'temperature_sensors' in temp_data:
            for sensor in temp_data['temperature_sensors']:
                temp_strings.append(f"{sensor['value']}{sensor['unit']}")
        
        # Параметры из prp
        if 'temperature_params' in temp_data:
            for key, value in temp_data['temperature_params'].items():
                # Сокращаем длинные имена
                short_key = key.replace('temperature', 't').replace('_', '')[:5]
                temp_strings.append(f"{value}°C")
        
        if temp_strings:
            # Возвращаем первые 3 значения, объединенные через запятую
            return ", ".join(temp_strings[:3])
        else:
            return "нет данных"
    
    def display_units(self, units: List[Dict]):
        """Отображение списка машин с пробегом и температурой"""
        if not units:
            print("Нет машин для отображения")
            return
        
        # Увеличиваем ширину таблицы для колонок с пробегом и температурой
        print("\n" + "="*200)
        print(f"{'№':<4} {'ID':<12} {'Название':<30} {'Статус':<12} {'Координаты':<30} {'Скорость':<8} {'Пробег (км)':<15} {'Температура':<25} {'Время':<8} {'Часовой пояс':<20}")
        print("="*200)
        
        for i, unit in enumerate(units, 1):
            unit_id = unit.get('id', 'Н/Д')
            name = unit.get('nm', 'Без имени')[:30]
            
            status = "🔴 Нет"
            coords = "нет данных"
            speed = "-"
            time_str = ""
            timezone = ""
            
            # Получаем пробег
            odometer = self.format_odometer(unit)
            
            # Получаем температуру
            temperature = self.format_temperature(unit)
            
            # Обработка позиции
            pos = unit.get('pos')
            if pos and isinstance(pos, dict):
                lat = pos.get('y', 0)
                lng = pos.get('x', 0)
                speed_val = pos.get('s', 0)
                
                if speed_val > 0:
                    status = f"🚗 {speed_val} км/ч"
                else:
                    status = "⏹️ Стоит"
                
                coords = f"{lat:.6f}, {lng:.6f}"
                speed = f"{speed_val}"
                
                if 't' in pos:
                    try:
                        dt = datetime.fromtimestamp(pos['t'])
                        time_str = dt.strftime('%H:%M')
                    except:
                        time_str = str(pos['t'])
                
                if lat != 0 and lng != 0:
                    timezone = self.get_timezone_from_coords(lat, lng)
                    # Сокращаем название часового пояса
                    if '/' in timezone:
                        timezone = timezone.split('/')[-1]
                else:
                    timezone = "нет"
            else:
                status = "📡 Нет сигнала"
            
            print(f"{i:<4} {unit_id:<12} {name:<30} {status:<12} {coords:<30} {speed:<8} {odometer:<15} {temperature:<25} {time_str:<8} {timezone:<20}")
        
        print("="*200)
        
        # Статистика
        total = len(units)
        with_pos = sum(1 for u in units if u.get('pos') and isinstance(u.get('pos'), dict))
        with_temp = sum(1 for u in units if self.extract_temperature_sensors(u))
        with_odometer = sum(1 for u in units if 'cnm' in u or ('prp' in u and ('odometer' in u['prp'] or 'mileage' in u['prp'])))
        
        print(f"\n📊 Статистика:")
        print(f"   Всего машин: {total}")
        print(f"   📍 С координатами: {with_pos}")
        print(f"   🌡️ С температурой: {with_temp}")
        print(f"   📏 С пробегом: {with_odometer}")
    
    def display_unit_details(self, unit: Dict):
        """Детальный вывод информации о машине"""
        if not unit:
            return
        
        print("\n" + "="*70)
        print(f"📋 ДЕТАЛЬНАЯ ИНФОРМАЦИЯ О МАШИНЕ")
        print("="*70)
        
        # Основная информация
        print(f"🆔 ID: {unit.get('id', 'Н/Д')}")
        print(f"📝 Название: {unit.get('nm', 'Н/Д')}")
        
        # Пробег
        print(f"\n📏 ПРОБЕГ:")
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
        
        # Температура - детальный вывод всех датчиков
        print(f"\n🌡️ ТЕМПЕРАТУРА:")
        temp_data = self.extract_temperature_sensors(unit)
        
        if temp_data:
            if 'temperature_sensors' in temp_data:
                print(f"   Датчики температуры:")
                for sensor in temp_data['temperature_sensors']:
                    print(f"     • {sensor['name']}: {sensor['value']}{sensor['unit']}")
            
            if 'temperature_params' in temp_data:
                print(f"   Параметры:")
                for key, value in temp_data['temperature_params'].items():
                    print(f"     • {key}: {value}°C")
            
            if 'temperature_counters' in temp_data:
                print(f"   Счетчики:")
                for key, value in temp_data['temperature_counters'].items():
                    print(f"     • {key}: {value}°C")
        else:
            print(f"   Нет данных о температуре")
        
        # Дополнительные счетчики
        if 'cneh' in unit:
            hours = unit['cneh']
            if isinstance(hours, (int, float)):
                hours_int = int(round(hours))
                print(f"\n⏱️ МОТОЧАСЫ: {hours_int} ч")
        
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
            
            if 't' in pos:
                try:
                    dt = datetime.fromtimestamp(pos['t'])
                    print(f"   Время: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
                except:
                    print(f"   Время (timestamp): {pos['t']}")
            
            if lat != 0 and lng != 0:
                timezone = self.get_timezone_from_coords(lat, lng)
                print(f"\n🌍 ЧАСОВОЙ ПОЯС: {timezone}")
                
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
    print("🚛 WIALON ТРЕКЕР - С ТЕМПЕРАТУРОЙ РЕФРИЖЕРАТОРА")
    print("="*60)
    print("1. 📋 Показать все машины")
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
                        show_details = input("\nПоказать детальную информацию? (д/н): ").strip().lower()
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
