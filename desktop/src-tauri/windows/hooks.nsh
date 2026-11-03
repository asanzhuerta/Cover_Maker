; Cover_Maker NSIS hooks (ADR-006).
;
; The per-user install folder is %LOCALAPPDATA%\Cover_Maker, which also holds
; the engine runtime (runtime\: Python, venv, PyTorch, ffmpeg, deno) and the
; user data (library, models, database, logs). The runtime belongs to the app:
; a real uninstall removes it. The user data goes only when "Delete the
; application data" is ticked. Updates keep both.

!macro NSIS_HOOK_POSTUNINSTALL
  ${If} $UpdateMode <> 1
    SetShellVarContext current
    RmDir /r "$LOCALAPPDATA\Cover_Maker\runtime"
    ${If} $DeleteAppDataCheckboxState = 1
      RmDir /r "$LOCALAPPDATA\Cover_Maker"
    ${EndIf}
  ${EndIf}
!macroend
