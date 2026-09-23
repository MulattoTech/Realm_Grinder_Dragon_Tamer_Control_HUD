import os
import sys
import win32com.client

def create_desktop_shortcut():
    wscript = win32com.client.Dispatch('WScript.Shell')
    desktop = wscript.SpecialFolders('Desktop')
    print('Desktop directory:', desktop)

    pythonw_exe = os.path.join(os.path.dirname(sys.executable), 'pythonw.exe')
    if not os.path.exists(pythonw_exe):
        pythonw_exe = sys.executable

    launcher_py = os.path.abspath('launcher.py')
    ico_path = os.path.abspath('assets/dragon_tamer.ico')
    work_dir = os.path.abspath('.')

    shortcut_names = [
        'Realm Grinder Dragon Tamer.lnk',
        'Dragon Tamer Bot.lnk'
    ]

    for name in shortcut_names:
        lnk_path = os.path.join(desktop, name)
        shortcut = wscript.CreateShortcut(lnk_path)
        shortcut.TargetPath = pythonw_exe
        shortcut.Arguments = f'"{launcher_py}"'
        shortcut.WorkingDirectory = work_dir
        shortcut.IconLocation = f'{ico_path},0'
        shortcut.Description = 'Autonomously plays Realm Grinder until Dragon Tamer achievement is earned'
        shortcut.Save()
        print(f'Created shortcut: {lnk_path}')
        print(f'  Target: {shortcut.TargetPath}')
        print(f'  Args: {shortcut.Arguments}')
        print(f'  Icon: {shortcut.IconLocation}')

if __name__ == '__main__':
    create_desktop_shortcut()
