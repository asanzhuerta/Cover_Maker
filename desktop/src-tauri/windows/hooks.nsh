; Cover_Maker NSIS hooks (ADR-006).
;
; The per-user install folder is %LOCALAPPDATA%\Cover_Maker, which also holds
; the engine runtime (runtime\: Python, venv, PyTorch, ffmpeg, deno) and the
; user data (library, models, database, logs). The runtime belongs to the app:
; a real uninstall removes it. The user data goes only when "Delete the
; application data" is ticked. Updates keep both.
;
; The language picked in the installer ($LANGUAGE, a Windows language id) is
; stored in HKCU\Software\Cover_Maker\Language; the app uses it as its default
; language on first start.

!macro NSIS_HOOK_POSTINSTALL
  WriteRegStr HKCU "Software\Cover_Maker" "Language" "$LANGUAGE"
!macroend

!macro NSIS_HOOK_POSTUNINSTALL
  ${If} $UpdateMode <> 1
    SetShellVarContext current
    DeleteRegKey HKCU "Software\Cover_Maker"
    RmDir /r "$LOCALAPPDATA\Cover_Maker\runtime"
    ${If} $DeleteAppDataCheckboxState = 1
      RmDir /r "$LOCALAPPDATA\Cover_Maker"
    ${EndIf}
  ${EndIf}
!macroend
