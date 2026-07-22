@echo off
chcp 65001 > nul
echo ==============================================================
echo iOS Mirror Capture 단독 설치 파일(EXE) 빌드 자동화 스크립트
echo ==============================================================
echo.
echo 이 스크립트는 다음 항목들이 준비되어 있어야 정상 동작합니다:
echo 1. MSYS2 환경 (C:\msys64) 내 uxplay.exe 및 ffmpeg.exe 빌드 완료 상태
echo 2. Python 환경 및 pyinstaller 설치 (없으면 자동 설치 시도)
echo 3. 동일 폴더 내에 Bonjour64.msi 파일 존재
echo 4. Inno Setup 6 설치 완료 (기본 경로: C:\Program Files (x86)\Inno Setup 6)
echo.
pause

echo [1/4] PyInstaller 및 필요한 Python 패키지 설치 중...
pip install pyinstaller pywin32
if errorlevel 1 (
    echo [오류] Python 패키지 설치에 실패했습니다. Python 환경을 확인하세요.
    pause
    exit /b
)
echo.

echo [2/4] Python 스크립트(.py)를 실행 파일로 변환 중 (폴더 모드)...
pyinstaller --noconfirm --name ios_mirror_capture ios_mirror_capture.py
if errorlevel 1 (
    echo [오류] PyInstaller 빌드에 실패했습니다.
    pause
    exit /b
)
echo.

echo [3/4] MSYS2 환경에서 의존성 파일 (uxplay, ffmpeg, dll 등) 복사 중...
python collect_deps.py
if errorlevel 1 (
    echo [오류] 의존성 파일 복사에 실패했습니다. MSYS2와 uxplay 빌드 상태를 확인하세요.
    pause
    exit /b
)
echo.

echo [4/4] Bonjour64.msi 확인 중...
if not exist "Bonjour64.msi" (
    echo [경고] Bonjour64.msi 파일이 현재 폴더에 없습니다.
    echo 윈도우 환경에 Bonjour SDK를 자동 설치하려면 Bonjour64.msi를 먼저 다운받아 이 폴더에 넣고 다시 실행해주세요.
    echo (다운로드 링크: https://developer.apple.com/download/all/?q=Bonjour%%20SDK%%20for%%20Windows)
    pause
    exit /b
)

echo [5/5] Inno Setup을 이용해 최종 통합 설치 파일(Setup.exe) 생성 중...
set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if exist %ISCC% (
    %ISCC% installer.iss
    echo.
    echo 빌드가 모두 완료되었습니다! Output 폴더 안의 Setup_iOSMirrorCapture.exe 를 확인하세요.
) else (
    echo [경고] Inno Setup 컴파일러(ISCC.exe)를 찾을 수 없습니다. (검색 경로: %ISCC%)
    echo Inno Setup 6를 설치하시거나, installer.iss 파일을 직접 우클릭하여 컴파일해주세요.
)
pause
