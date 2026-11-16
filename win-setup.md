 *  Executing task in folder koppelvlakspecificatie-netwerkmodel: powershell -ExecutionPolicy Bypass -c 'irm https://astral.sh/uv/install.ps1 | iex' 

downloading uv 0.13.8 (x86_64-pc-windows-msvc)
installing to C:\Users\RVR\.local\bin                                                                                                                                                       
  uv.exe
  uvx.exe
  uvw.exe
everything's installed!

To add C:\Users\RVR\.local\bin to your PATH, either restart your shell or run:

    set Path=C:\Users\RVR\.local\bin;%Path%   (cmd)
    $env:Path = "C:\Users\RVR\.local\bin;$env:Path"   (powershell)

 *  Executing task in folder koppelvlakspecificatie-netwerkmodel: C:\Users\RVR\.local\bin\uv.exe python install 

Installed Python 3.15.2 in 7.80s
 + cpython-3.15.2-windows-x86_64-none (python3.15.exe)
warning: `C:\Users\RVR\.local\bin` is not on your PATH. To use installed Python executables, run `$env:PATH = "C:\Users\RVR\.local\bin;$env:PATH"` or `uv python update-shell`.


-- 
```bash
$env:Path = "C:\Users\RVR\.local\bin;$env:Path" 
python3.15 -m venv venv
```