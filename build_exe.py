"""
Build script for RandomVideoJoiner
Creates a standalone .exe file using PyInstaller
"""

import os
import sys
import subprocess

def install_pyinstaller():
    """Install PyInstaller if not already installed"""
    print("📦 Checking PyInstaller...")
    try:
        import PyInstaller
        print("✅ PyInstaller already installed")
    except ImportError:
        print("📥 Installing PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        print("✅ PyInstaller installed successfully")

def build_exe():
    """Build the executable using PyInstaller"""
    print("\n🔨 Building RandomVideoJoiner.exe...")
    
    # Get the directory of this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # PyInstaller command
    cmd = [
        "pyinstaller",
        "--name=RandomVideoJoiner",
        "--onefile",                    # Single exe file
        "--windowed",                   # No console window
        "--clean",                      # Clean cache
        "main.py"
    ]
    
    print(f"📝 Command: {' '.join(cmd)}")
    
    try:
        subprocess.check_call(cmd, cwd=script_dir)
        print("\n✅ Build completed successfully!")
        print(f"📁 Executable location: {os.path.join(script_dir, 'dist', 'RandomVideoJoiner.exe')}")
        print("\n🎉 You can now run RandomVideoJoiner.exe from the dist folder!")
        print("\n⚠️  IMPORTANT: FFmpeg must be installed and in PATH for the app to work!")
        
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Build failed: {e}")
        sys.exit(1)

def main():
    print("=" * 60)
    print("  RandomVideoJoiner - Build to EXE")
    print("=" * 60)
    
    # Step 1: Install PyInstaller
    install_pyinstaller()
    
    # Step 2: Build executable
    build_exe()
    
    print("\n" + "=" * 60)
    print("  Build process completed!")
    print("=" * 60)

if __name__ == "__main__":
    main()
