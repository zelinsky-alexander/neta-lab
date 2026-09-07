# Third-Party Notices

No third-party source code is vendored in this repository.

The initial scenarios invoke tools supplied by the test environment:

- Python 3 standard library — Python Software Foundation License; used for the controlled HTTP/HTTPS server. Python is actively maintained. No known project-specific licensing concern from use of the standard library.
- curl executable — curl license (MIT-style); used to issue controlled HTTP/HTTPS requests. curl is actively maintained. No known major licensing concern for invoking the installed executable.
- PowerShell — MIT License; used to orchestrate the Windows client loop. PowerShell is actively maintained. No known major licensing concern for running local scripts.
- OpenSSL executable — Apache License 2.0 for current OpenSSL releases; used only by the documented operator command to generate a temporary self-signed lab certificate. OpenSSL is actively maintained. Users should keep their system package patched for security updates.

These tools are not redistributed by NETA Lab. Their licenses remain governed by their respective projects and system distributions.
