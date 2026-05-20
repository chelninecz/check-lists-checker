import tkinter as tk
from tkinter import filedialog, messagebox
import os
import time
import threading
from pathlib import Path
from plyer import notification
import win32gui
import win32con
import win32api

class TrayApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()  # Скрываем главное окно
        
        # Путь по умолчанию
        self.default_folder = r"\\10.16.130.100\WMFactory\QA_DPT\IQC Task\38 Специалист\06 Сканы тестовых чек-листов"
        self.folder_path = self.default_folder
        
        # Интервал сканирования (в секундах)
        self.scan_interval = 3600  # 1 час
        
        # Множество известных файлов
        self.known_files = set()
        
        # Флаг остановки
        self.running = True
        
        # Создаем иконку в трее
        self.setup_tray_icon()
        
        # Запускаем сканирование в отдельном потоке
        self.scan_thread = threading.Thread(target=self.scan_loop, daemon=True)
        self.scan_thread.start()
        
        # Инициализируем список файлов при запуске
        self.initialize_files()
    
    def setup_tray_icon(self):
        """Настройка иконки в системном трее"""
        self.hwnd = None
        
        # Класс окна
        wc = win32gui.WNDCLASS()
        wc.hInstance = win32api.GetModuleHandle(None)
        wc.lpszClassName = "TrayAppClass"
        wc.lpfnWndProc = {
            win32con.WM_DESTROY: self.on_destroy,
        }
        class_atom = win32gui.RegisterClass(wc)
        
        # Создаем окно
        style = win32con.WS_OVERLAPPED | win32con.WS_SYSMENU
        self.hwnd = win32gui.CreateWindow(
            class_atom, "Tray App", style,
            0, 0, win32con.CW_USEDEFAULT, win32con.CW_USEDEFAULT,
            None, None, wc.hInstance, None
        )
        
        # Создаем меню трея
        menu = win32gui.CreatePopupMenu()
        win32gui.AppendMenu(menu, win32con.MF_STRING, 1001, "Выбрать папку")
        win32gui.AppendMenu(menu, win32con.MF_STRING, 1002, "Сканировать сейчас")
        win32gui.AppendMenu(menu, win32con.MF_SEPARATOR, 0, "")
        win32gui.AppendMenu(menu, win32con.MF_STRING, 1003, "Выход")
        
        # Иконка (используем стандартную)
        icon_flags = win32con.LR_LOADFROMFILE | win32con.LR_DEFAULTSIZE
        try:
            # Пытаемся использовать стандартную иконку Python
            icon_path = os.path.join(os.path.dirname(__file__), "icon.ico")
            if os.path.exists(icon_path):
                hicon = win32gui.LoadImage(
                    None, icon_path, win32con.IMAGE_ICON,
                    0, 0, icon_flags
                )
            else:
                hicon = win32gui.LoadIcon(None, win32con.IDI_APPLICATION)
        except:
            hicon = win32gui.LoadIcon(None, win32con.IDI_APPLICATION)
        
        # Добавляем иконку в трей
        nid = (self.hwnd, 0, win32gui.NIF_ICON | win32gui.NIF_MESSAGE | win32gui.NIF_TIP,
               win32con.WM_USER + 20, hicon, "PDF Scanner")
        win32gui.Shell_NotifyIcon(win32gui.NIM_ADD, nid)
        
        self.menu = menu
        self.nid = nid
    
    def on_destroy(self, hwnd, msg, wparam, lparam):
        """Обработчик уничтожения окна"""
        self.running = False
        win32gui.Shell_NotifyIcon(win32gui.NIM_DELETE, self.nid)
        win32gui.PostQuitMessage(0)
        return 0
    
    def initialize_files(self):
        """Инициализация списка известных файлов"""
        try:
            if os.path.exists(self.folder_path):
                for file in os.listdir(self.folder_path):
                    if file.lower().endswith('.pdf'):
                        self.known_files.add(file)
        except Exception as e:
            print(f"Ошибка при инициализации файлов: {e}")
    
    def scan_folder(self):
        """Сканирование папки на наличие новых файлов"""
        try:
            if not os.path.exists(self.folder_path):
                print(f"Папка не найдена: {self.folder_path}")
                return
            
            current_files = set()
            for file in os.listdir(self.folder_path):
                if file.lower().endswith('.pdf'):
                    current_files.add(file)
            
            # Находим новые файлы
            new_files = current_files - self.known_files
            
            for new_file in new_files:
                # Показываем уведомление
                self.show_notification(new_file)
                # Добавляем файл в известные
                self.known_files.add(new_file)
            
            # Обновляем множество известных файлов
            self.known_files = current_files
            
        except Exception as e:
            print(f"Ошибка при сканировании: {e}")
    
    def show_notification(self, filename):
        """Показ уведомления Windows"""
        try:
            notification.notify(
                title="Новый файл обнаружен",
                message=f"Новый файл: {filename}",
                app_name="PDF Scanner",
                timeout=5  # Уведомление исчезнет через 5 секунд
            )
        except Exception as e:
            print(f"Ошибка при показе уведомления: {e}")
    
    def scan_loop(self):
        """Основной цикл сканирования"""
        while self.running:
            self.scan_folder()
            # Ждем следующий интервал сканирования
            for _ in range(self.scan_interval):
                if not self.running:
                    break
                time.sleep(1)
    
    def select_folder(self):
        """Диалог выбора папки"""
        folder = filedialog.askdirectory(
            initialdir=self.folder_path,
            title="Выберите папку для сканирования"
        )
        if folder:
            self.folder_path = folder
            self.known_files.clear()
            self.initialize_files()
            messagebox.showinfo("Успешно", f"Папка изменена на:\n{folder}")
    
    def manual_scan(self):
        """Ручное сканирование"""
        self.scan_folder()
        messagebox.showinfo("Сканирование завершено", "Проверка папки выполнена")
    
    def run(self):
        """Запуск приложения"""
        # Обработка сообщений меню трея
        def wnd_proc(hwnd, msg, wparam, lparam):
            if msg == win32con.WM_USER + 20:
                if lparam == win32con.WM_RBUTTONUP:
                    # Показываем меню при клике правой кнопкой
                    pos = win32gui.GetCursorPos()
                    win32gui.SetForegroundWindow(hwnd)
                    win32gui.TrackPopupMenu(
                        self.menu,
                        win32con.TPM_LEFTALIGN,
                        pos[0], pos[1], 0, hwnd, None
                    )
                    win32gui.PostMessage(hwnd, win32con.WM_NULL, 0, 0)
            return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)
        
        # Перехватываем сообщения окна
        old_proc = win32gui.SetWindowLong(self.hwnd, win32con.GWL_WNDPROC, wnd_proc)
        
        # Запускаем главный цикл
        self.root.mainloop()

if __name__ == "__main__":
    app = TrayApp()
    app.run()
