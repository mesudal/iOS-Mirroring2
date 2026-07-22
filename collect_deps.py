import os
import shutil
import glob
import sys

def main():
    dist_bin = r"dist\ios_mirror_capture\bin"
    os.makedirs(dist_bin, exist_ok=True)
    
    msys_bin = r"C:\msys64\ucrt64\bin"
    
    # 1. Find uxplay.exe
    uxplay_paths = glob.glob(r"C:\msys64\home\*\UxPlay\build\uxplay.exe")
    if not uxplay_paths:
        print("Error: Could not find uxplay.exe in C:\\msys64\\home\\*\\UxPlay\\build\\")
        print("Please build it first using MSYS2 and build_uxplay.sh")
        sys.exit(1)
        
    uxplay_src = uxplay_paths[0]
    print(f"Found uxplay: {uxplay_src}")
    shutil.copy2(uxplay_src, os.path.join(dist_bin, "uxplay.exe"))
    
    # 2. Find ffmpeg.exe
    ffmpeg_src = os.path.join(msys_bin, "ffmpeg.exe")
    if not os.path.exists(ffmpeg_src):
        print(f"Error: Could not find {ffmpeg_src}")
        sys.exit(1)
        
    print(f"Found ffmpeg: {ffmpeg_src}")
    shutil.copy2(ffmpeg_src, os.path.join(dist_bin, "ffmpeg.exe"))
    
    # 3. Copy all DLLs from MSYS2 UCRT64 bin
    # We copy all to ensure GStreamer plugins, ffmpeg libs, and libplist are included
    print(f"Copying DLLs from {msys_bin} to {dist_bin}...")
    dlls = glob.glob(os.path.join(msys_bin, "*.dll"))
    for dll in dlls:
        shutil.copy2(dll, dist_bin)
        
    print(f"Success! {len(dlls)} DLLs and executables copied to {dist_bin}")
    
    # 4. Copy GStreamer plugins
    gst_plugins_src = r"C:\msys64\ucrt64\lib\gstreamer-1.0"
    gst_plugins_dest = os.path.join(dist_bin, "gstreamer-plugins")
    if os.path.exists(gst_plugins_src):
        print(f"Copying GStreamer plugins from {gst_plugins_src} to {gst_plugins_dest}...")
        if os.path.exists(gst_plugins_dest):
            shutil.rmtree(gst_plugins_dest)
        shutil.copytree(gst_plugins_src, gst_plugins_dest)
        print("GStreamer plugins copied.")
    else:
        print(f"Warning: GStreamer plugins directory not found at {gst_plugins_src}")

if __name__ == "__main__":
    main()
