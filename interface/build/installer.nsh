; Instalador assistido do Eterzion Studio.
;
; O electron-builder inclui este arquivo ANTES do installer.nsi, quando o MUI,
; o nsDialogs e os idiomas ainda nao existem. Por isso tudo o que usa esses
; recursos mora dentro de macros, que o template insere depois:
;
;   customHeader              topo, depois do addLangs     -> as LangStrings
;   customInit                .onInit do instalador        -> padrao das caixas
;   customPageAfterChangeDir  entre "pasta" e "instalar"   -> pagina de Opcoes
;   customInstall             fim da secao de instalacao   -> aplica as escolhas
;   customUnInit              .onInit do desinstalador     -> padrao da limpeza
;   customUnWelcomePage       antes de desinstalar         -> pagina de limpeza
;   customUnInstall           antes de apagar os arquivos  -> limpeza de dados
;
; O `warningsAsErrors` do electron-builder transforma variavel ou funcao sem
; uso em erro de compilacao. O instalador e o desinstalador sao compilados
; separadamente, entao o que e' so' de um fica atras de BUILD_UNINSTALLER.
;
; Estas paginas nunca aparecem numa atualizacao automatica: o electron-updater
; roda o instalador com /S --updated, e o NSIS nao mostra paginas em /S. A
; pagina de Opcoes ainda confere ${isUpdated}, para o caso de uma atualizacao
; ser executada com interface.

; ---------------------------------------------------------------- textos
; Os 11 idiomas do app, na ordem de installerLanguages (electron-builder.yml).
; Toda LangString precisa existir em todos eles: faltar uma e' aviso, e aviso
; e' erro. O teste src/main/__tests__/installerNsh.spec.ts confere isso antes
; do build, que e' onde o erro apareceria.
!macro customHeader
  LangString ezOpcoesTitulo ${LANG_ENGLISH} "Installation options"
  LangString ezOpcoesTitulo ${LANG_PORTUGUESEBR} "Opções de instalação"
  LangString ezOpcoesTitulo ${LANG_PORTUGUESE} "Opções de instalação"
  LangString ezOpcoesTitulo ${LANG_SPANISHINTERNATIONAL} "Opciones de instalación"
  LangString ezOpcoesTitulo ${LANG_FRENCH} "Options d'installation"
  LangString ezOpcoesTitulo ${LANG_GERMAN} "Installationsoptionen"
  LangString ezOpcoesTitulo ${LANG_ITALIAN} "Opzioni di installazione"
  LangString ezOpcoesTitulo ${LANG_JAPANESE} "インストール オプション"
  LangString ezOpcoesTitulo ${LANG_KOREAN} "설치 옵션"
  LangString ezOpcoesTitulo ${LANG_RUSSIAN} "Параметры установки"
  LangString ezOpcoesTitulo ${LANG_SIMPCHINESE} "安装选项"
  LangString ezOpcoesSubtitulo ${LANG_ENGLISH} "Choose how Eterzion Studio will be installed."
  LangString ezOpcoesSubtitulo ${LANG_PORTUGUESEBR} "Escolha como o Eterzion Studio será instalado."
  LangString ezOpcoesSubtitulo ${LANG_PORTUGUESE} "Escolha como o Eterzion Studio será instalado."
  LangString ezOpcoesSubtitulo ${LANG_SPANISHINTERNATIONAL} "Elige cómo se instalará Eterzion Studio."
  LangString ezOpcoesSubtitulo ${LANG_FRENCH} "Choisissez comment Eterzion Studio sera installé."
  LangString ezOpcoesSubtitulo ${LANG_GERMAN} "Wählen Sie, wie Eterzion Studio installiert wird."
  LangString ezOpcoesSubtitulo ${LANG_ITALIAN} "Scegli come installare Eterzion Studio."
  LangString ezOpcoesSubtitulo ${LANG_JAPANESE} "Eterzion Studio のインストール方法を選択してください。"
  LangString ezOpcoesSubtitulo ${LANG_KOREAN} "Eterzion Studio 설치 방법을 선택하세요."
  LangString ezOpcoesSubtitulo ${LANG_RUSSIAN} "Выберите, как установить Eterzion Studio."
  LangString ezOpcoesSubtitulo ${LANG_SIMPCHINESE} "选择 Eterzion Studio 的安装方式。"
  LangString ezOpcoesAtalho ${LANG_ENGLISH} "Create a desktop shortcut"
  LangString ezOpcoesAtalho ${LANG_PORTUGUESEBR} "Criar atalho na área de trabalho"
  LangString ezOpcoesAtalho ${LANG_PORTUGUESE} "Criar atalho no ambiente de trabalho"
  LangString ezOpcoesAtalho ${LANG_SPANISHINTERNATIONAL} "Crear un acceso directo en el escritorio"
  LangString ezOpcoesAtalho ${LANG_FRENCH} "Créer un raccourci sur le bureau"
  LangString ezOpcoesAtalho ${LANG_GERMAN} "Verknüpfung auf dem Desktop erstellen"
  LangString ezOpcoesAtalho ${LANG_ITALIAN} "Crea un collegamento sul desktop"
  LangString ezOpcoesAtalho ${LANG_JAPANESE} "デスクトップにショートカットを作成する"
  LangString ezOpcoesAtalho ${LANG_KOREAN} "바탕 화면에 바로 가기 만들기"
  LangString ezOpcoesAtalho ${LANG_RUSSIAN} "Создать ярлык на рабочем столе"
  LangString ezOpcoesAtalho ${LANG_SIMPCHINESE} "创建桌面快捷方式"
  LangString ezOpcoesModelos ${LANG_ENGLISH} "Download the AI models after activating the license (about 130 MB)"
  LangString ezOpcoesModelos ${LANG_PORTUGUESEBR} "Baixar os modelos de IA depois de ativar a licença (cerca de 130 MB)"
  LangString ezOpcoesModelos ${LANG_PORTUGUESE} "Transferir os modelos de IA depois de ativar a licença (cerca de 130 MB)"
  LangString ezOpcoesModelos ${LANG_SPANISHINTERNATIONAL} "Descargar los modelos de IA después de activar la licencia (unos 130 MB)"
  LangString ezOpcoesModelos ${LANG_FRENCH} "Télécharger les modèles d'IA après l'activation de la licence (environ 130 Mo)"
  LangString ezOpcoesModelos ${LANG_GERMAN} "KI-Modelle nach der Lizenzaktivierung herunterladen (ca. 130 MB)"
  LangString ezOpcoesModelos ${LANG_ITALIAN} "Scarica i modelli di IA dopo aver attivato la licenza (circa 130 MB)"
  LangString ezOpcoesModelos ${LANG_JAPANESE} "ライセンスの有効化後に AI モデルをダウンロードする（約 130 MB）"
  LangString ezOpcoesModelos ${LANG_KOREAN} "라이선스 활성화 후 AI 모델 다운로드(약 130MB)"
  LangString ezOpcoesModelos ${LANG_RUSSIAN} "Загрузить модели ИИ после активации лицензии (около 130 МБ)"
  LangString ezOpcoesModelos ${LANG_SIMPCHINESE} "激活许可证后下载 AI 模型（约 130 MB）"
  LangString ezOpcoesModelosNota ${LANG_ENGLISH} "Otherwise, each model is downloaded the first time it is used."
  LangString ezOpcoesModelosNota ${LANG_PORTUGUESEBR} "Sem isso, cada modelo é baixado na primeira vez em que for usado."
  LangString ezOpcoesModelosNota ${LANG_PORTUGUESE} "Caso contrário, cada modelo é transferido na primeira vez que for utilizado."
  LangString ezOpcoesModelosNota ${LANG_SPANISHINTERNATIONAL} "Si no, cada modelo se descarga la primera vez que se usa."
  LangString ezOpcoesModelosNota ${LANG_FRENCH} "Sinon, chaque modèle est téléchargé lors de sa première utilisation."
  LangString ezOpcoesModelosNota ${LANG_GERMAN} "Andernfalls wird jedes Modell bei der ersten Verwendung heruntergeladen."
  LangString ezOpcoesModelosNota ${LANG_ITALIAN} "Altrimenti, ogni modello viene scaricato al primo utilizzo."
  LangString ezOpcoesModelosNota ${LANG_JAPANESE} "オフにすると、各モデルは初めて使うときにダウンロードされます。"
  LangString ezOpcoesModelosNota ${LANG_KOREAN} "선택하지 않으면 각 모델은 처음 사용할 때 다운로드됩니다."
  LangString ezOpcoesModelosNota ${LANG_RUSSIAN} "Иначе каждая модель загружается при первом использовании."
  LangString ezOpcoesModelosNota ${LANG_SIMPCHINESE} "否则，每个模型会在首次使用时下载。"
  LangString ezAvisoTodos ${LANG_ENGLISH} "You chose to install for all users: Windows will also ask for administrator permission on every update."
  LangString ezAvisoTodos ${LANG_PORTUGUESEBR} "Você escolheu instalar para todos os usuários: o Windows vai pedir permissão de administrador também a cada atualização."
  LangString ezAvisoTodos ${LANG_PORTUGUESE} "Escolheu instalar para todos os utilizadores: o Windows vai pedir permissão de administrador também em cada atualização."
  LangString ezAvisoTodos ${LANG_SPANISHINTERNATIONAL} "Elegiste instalar para todos los usuarios: Windows también pedirá permiso de administrador en cada actualización."
  LangString ezAvisoTodos ${LANG_FRENCH} "Vous avez choisi d'installer pour tous les utilisateurs : Windows demandera aussi l'autorisation d'administrateur à chaque mise à jour."
  LangString ezAvisoTodos ${LANG_GERMAN} "Sie haben die Installation für alle Benutzer gewählt: Windows fragt auch bei jedem Update nach Administratorrechten."
  LangString ezAvisoTodos ${LANG_ITALIAN} "Hai scelto di installare per tutti gli utenti: Windows chiederà l'autorizzazione di amministratore anche a ogni aggiornamento."
  LangString ezAvisoTodos ${LANG_JAPANESE} "すべてのユーザー向けのインストールを選択しました。更新のたびにも Windows が管理者の許可を求めます。"
  LangString ezAvisoTodos ${LANG_KOREAN} "모든 사용자용 설치를 선택했습니다. 업데이트할 때마다 Windows에서 관리자 권한도 요청합니다."
  LangString ezAvisoTodos ${LANG_RUSSIAN} "Вы выбрали установку для всех пользователей: Windows будет запрашивать права администратора и при каждом обновлении."
  LangString ezAvisoTodos ${LANG_SIMPCHINESE} "你选择了为所有用户安装：每次更新时 Windows 也会请求管理员权限。"
  LangString ezDesinstTitulo ${LANG_ENGLISH} "Eterzion Studio data"
  LangString ezDesinstTitulo ${LANG_PORTUGUESEBR} "Dados do Eterzion Studio"
  LangString ezDesinstTitulo ${LANG_PORTUGUESE} "Dados do Eterzion Studio"
  LangString ezDesinstTitulo ${LANG_SPANISHINTERNATIONAL} "Datos de Eterzion Studio"
  LangString ezDesinstTitulo ${LANG_FRENCH} "Données d'Eterzion Studio"
  LangString ezDesinstTitulo ${LANG_GERMAN} "Daten von Eterzion Studio"
  LangString ezDesinstTitulo ${LANG_ITALIAN} "Dati di Eterzion Studio"
  LangString ezDesinstTitulo ${LANG_JAPANESE} "Eterzion Studio のデータ"
  LangString ezDesinstTitulo ${LANG_KOREAN} "Eterzion Studio 데이터"
  LangString ezDesinstTitulo ${LANG_RUSSIAN} "Данные Eterzion Studio"
  LangString ezDesinstTitulo ${LANG_SIMPCHINESE} "Eterzion Studio 数据"
  LangString ezDesinstSubtitulo ${LANG_ENGLISH} "Choose what to remove besides the app."
  LangString ezDesinstSubtitulo ${LANG_PORTUGUESEBR} "Escolha o que remover além do aplicativo."
  LangString ezDesinstSubtitulo ${LANG_PORTUGUESE} "Escolha o que remover além da aplicação."
  LangString ezDesinstSubtitulo ${LANG_SPANISHINTERNATIONAL} "Elige qué eliminar además de la aplicación."
  LangString ezDesinstSubtitulo ${LANG_FRENCH} "Choisissez ce qu'il faut supprimer en plus de l'application."
  LangString ezDesinstSubtitulo ${LANG_GERMAN} "Wählen Sie, was außer der App entfernt werden soll."
  LangString ezDesinstSubtitulo ${LANG_ITALIAN} "Scegli cosa rimuovere oltre all'app."
  LangString ezDesinstSubtitulo ${LANG_JAPANESE} "アプリ以外に削除するものを選択してください。"
  LangString ezDesinstSubtitulo ${LANG_KOREAN} "앱 외에 제거할 항목을 선택하세요."
  LangString ezDesinstSubtitulo ${LANG_RUSSIAN} "Выберите, что удалить помимо приложения."
  LangString ezDesinstSubtitulo ${LANG_SIMPCHINESE} "选择除应用外还要删除的内容。"
  LangString ezDesinstLimpar ${LANG_ENGLISH} "Also remove AI models, settings and history"
  LangString ezDesinstLimpar ${LANG_PORTUGUESEBR} "Remover também modelos de IA, configurações e histórico"
  LangString ezDesinstLimpar ${LANG_PORTUGUESE} "Remover também modelos de IA, definições e histórico"
  LangString ezDesinstLimpar ${LANG_SPANISHINTERNATIONAL} "Eliminar también los modelos de IA, la configuración y el historial"
  LangString ezDesinstLimpar ${LANG_FRENCH} "Supprimer aussi les modèles d'IA, les paramètres et l'historique"
  LangString ezDesinstLimpar ${LANG_GERMAN} "Auch KI-Modelle, Einstellungen und Verlauf entfernen"
  LangString ezDesinstLimpar ${LANG_ITALIAN} "Rimuovi anche i modelli di IA, le impostazioni e la cronologia"
  LangString ezDesinstLimpar ${LANG_JAPANESE} "AI モデル、設定、履歴も削除する"
  LangString ezDesinstLimpar ${LANG_KOREAN} "AI 모델, 설정 및 기록도 제거"
  LangString ezDesinstLimpar ${LANG_RUSSIAN} "Также удалить модели ИИ, настройки и историю"
  LangString ezDesinstLimpar ${LANG_SIMPCHINESE} "同时删除 AI 模型、设置和历史记录"
  LangString ezDesinstNota ${LANG_ENGLISH} "Your license activation is kept: if you reinstall, you won't need to activate again."
  LangString ezDesinstNota ${LANG_PORTUGUESEBR} "A ativação da licença é mantida: se reinstalar, você não precisa ativar de novo."
  LangString ezDesinstNota ${LANG_PORTUGUESE} "A ativação da licença é mantida: se reinstalar, não precisa de ativar novamente."
  LangString ezDesinstNota ${LANG_SPANISHINTERNATIONAL} "La activación de la licencia se conserva: si reinstalas, no tendrás que activarla de nuevo."
  LangString ezDesinstNota ${LANG_FRENCH} "L'activation de la licence est conservée : si vous réinstallez, vous n'aurez pas à la réactiver."
  LangString ezDesinstNota ${LANG_GERMAN} "Die Lizenzaktivierung bleibt erhalten: Bei einer Neuinstallation müssen Sie sie nicht erneut aktivieren."
  LangString ezDesinstNota ${LANG_ITALIAN} "L'attivazione della licenza viene mantenuta: se reinstalli, non dovrai attivarla di nuovo."
  LangString ezDesinstNota ${LANG_JAPANESE} "ライセンスの有効化は保持されます。再インストールしても、再度有効化する必要はありません。"
  LangString ezDesinstNota ${LANG_KOREAN} "라이선스 활성화는 유지됩니다. 다시 설치해도 다시 활성화할 필요가 없습니다."
  LangString ezDesinstNota ${LANG_RUSSIAN} "Активация лицензии сохраняется: при переустановке активировать заново не потребуется."
  LangString ezDesinstNota ${LANG_SIMPCHINESE} "许可证激活会保留：重新安装后无需再次激活。"
!macroend

!ifndef BUILD_UNINSTALLER
  ; ------------------------------------------------------------ instalador
  Var EzCriarAtalho
  Var EzBaixarModelos
  Var EzChkAtalho
  Var EzChkModelos

  !macro customInit
    ; Marcadas por padrao. Tambem vale para a instalacao silenciosa de um
    ; administrador (/S sem --updated), que nao passa pela pagina.
    StrCpy $EzCriarAtalho "1"
    StrCpy $EzBaixarModelos "1"
  !macroend

  !macro customPageAfterChangeDir
    !include nsDialogs.nsh
    Page custom ezOpcoesPre ezOpcoesLeave

    Function ezOpcoesPre
      ${if} ${isUpdated}
        Abort
      ${endif}
      !insertmacro MUI_HEADER_TEXT "$(ezOpcoesTitulo)" "$(ezOpcoesSubtitulo)"
      nsDialogs::Create 1018
      Pop $0
      ${if} $0 == error
        Abort
      ${endif}

      ${NSD_CreateCheckbox} 0 0 100% 12u "$(ezOpcoesAtalho)"
      Pop $EzChkAtalho
      ${if} $EzCriarAtalho == "1"
        ${NSD_Check} $EzChkAtalho
      ${endif}

      ${NSD_CreateCheckbox} 0 22u 100% 12u "$(ezOpcoesModelos)"
      Pop $EzChkModelos
      ${if} $EzBaixarModelos == "1"
        ${NSD_Check} $EzChkModelos
      ${endif}
      ${NSD_CreateLabel} 12u 36u 95% 20u "$(ezOpcoesModelosNota)"
      Pop $0

      ; Quem escolheu "para todos" na pagina anterior precisa saber, antes de
      ; instalar, que cada atualizacao tambem vai pedir administrador. O texto
      ; da propria pagina de modo so' fala da instalacao, e e' do
      ; electron-builder: redefini-lo duplicaria uma LangString (erro).
      ${if} $installMode == "all"
        ${NSD_CreateLabel} 0 84u 100% 30u "$(ezAvisoTodos)"
        Pop $0
      ${endif}

      nsDialogs::Show
    FunctionEnd

    Function ezOpcoesLeave
      ${NSD_GetState} $EzChkAtalho $0
      ${if} $0 == ${BST_CHECKED}
        StrCpy $EzCriarAtalho "1"
      ${else}
        StrCpy $EzCriarAtalho "0"
      ${endif}
      ${NSD_GetState} $EzChkModelos $0
      ${if} $0 == ${BST_CHECKED}
        StrCpy $EzBaixarModelos "1"
      ${else}
        StrCpy $EzBaixarModelos "0"
      ${endif}
    FunctionEnd
  !macroend

  !macro customInstall
    ${ifNot} ${isUpdated}
      ; O template ja' criou o atalho (createDesktopShortcut: true). Desmarcado,
      ; ele sai aqui. Numa atualizacao o template nao recria atalho que nao
      ; existe, entao a escolha da pessoa se mantem sozinha.
      ${if} $EzCriarAtalho != "1"
        WinShell::UninstShortcut "$newDesktopLink"
        Delete "$newDesktopLink"
      ${endif}

      ; O app le este arquivo ao abrir (src/main/installerOptions.ts). Fica na
      ; pasta do app porque ela e' legivel por todas as contas numa instalacao
      ; "para todos". Vive ate' a proxima atualizacao, que recria a pasta; o
      ; app guarda a decisao no userData de cada conta antes disso.
      ${if} $EzBaixarModelos == "1"
        FileOpen $0 "$INSTDIR\installer-options.json" w
        FileWrite $0 '{"downloadModelsAfterActivation":true}'
        FileClose $0
      ${endif}
    ${endIf}
  !macroend
!else
  ; ---------------------------------------------------------- desinstalador
  Var EzLimparDados
  Var EzChkLimpar

  !macro customUnInit
    StrCpy $EzLimparDados "0"
  !macroend

  !macro customUnWelcomePage
    !insertmacro MUI_UNPAGE_WELCOME
    !include nsDialogs.nsh
    UninstPage custom un.ezLimparPre un.ezLimparLeave

    Function un.ezLimparPre
      !insertmacro MUI_HEADER_TEXT "$(ezDesinstTitulo)" "$(ezDesinstSubtitulo)"
      nsDialogs::Create 1018
      Pop $0
      ${if} $0 == error
        Abort
      ${endif}
      ${NSD_CreateCheckbox} 0 0 100% 12u "$(ezDesinstLimpar)"
      Pop $EzChkLimpar
      ${NSD_CreateLabel} 12u 16u 95% 24u "$(ezDesinstNota)"
      Pop $0
      nsDialogs::Show
    FunctionEnd

    Function un.ezLimparLeave
      ${NSD_GetState} $EzChkLimpar $0
      ${if} $0 == ${BST_CHECKED}
        StrCpy $EzLimparDados "1"
      ${else}
        StrCpy $EzLimparDados "0"
      ${endif}
    FunctionEnd
  !macroend

  !macro customUnInstall
    ; Nunca numa atualizacao: o instalador novo roda o desinstalador antigo com
    ; --updated antes de copiar os arquivos.
    ${ifNot} ${isUpdated}
    ${andIf} $EzLimparDados == "1"
      ; Estas pastas sao de cada conta. Numa instalacao "para todos" o contexto
      ; esta' em "all", e $APPDATA/$LOCALAPPDATA apontariam para ProgramData.
      ${if} $installMode == "all"
        SetShellVarContext current
      ${endif}

      ; Caminhos literais, nunca montados de variavel: um RMDir /r sobre
      ; "$LOCALAPPDATA\" com o nome vazio apagaria o AppData inteiro.
      RMDir /r "$APPDATA\eterzion-studio"
      RMDir /r "$LOCALAPPDATA\eterzion-studio"
      RMDir /r "$LOCALAPPDATA\eterzion-studio-worker"
      RMDir /r "$LOCALAPPDATA\eterzion-studio-updater"
      ; Na ordem: configuracoes, historico e saidas internas (userData);
      ; modelos (src/main/modelsDir.ts); temporarios do worker (security.py);
      ; instaladores baixados pelo electron-updater.
      ;
      ; %LOCALAPPDATA%\AstrosUpscale fica, de proposito: e' a identidade da
      ; ativacao. Apaga-la faria uma reinstalacao gastar outra vaga da licenca.

      ${if} $installMode == "all"
        SetShellVarContext all
      ${endif}
    ${endIf}
  !macroend
!endif
