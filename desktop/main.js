/**
 * ROI Max para macOS.
 *
 * Uma casca nativa em volta da mesma interface. O que ela resolve e um
 * navegador não resolve:
 *   - ícone no Dock e no Launchpad, sem barra de endereço à vista
 *   - o link "Abrir na Betfair" vai para o navegador padrão, onde a sua
 *     sessão da Betfair já está logada (dentro do app você estaria deslogado)
 *   - o endereço do servidor fica guardado, então não há localhost para digitar
 */
const { app, BrowserWindow, Menu, shell, dialog, nativeTheme } = require("electron");
const fs = require("node:fs");
const path = require("node:path");

const CONFIG = () => path.join(app.getPath("userData"), "config.json");

function readConfig() {
  try {
    return JSON.parse(fs.readFileSync(CONFIG(), "utf8"));
  } catch {
    return {};
  }
}

function writeConfig(patch) {
  const next = { ...readConfig(), ...patch };
  fs.mkdirSync(path.dirname(CONFIG()), { recursive: true });
  fs.writeFileSync(CONFIG(), JSON.stringify(next, null, 2));
  return next;
}

let win = null;

function load() {
  const { serverUrl } = readConfig();
  if (serverUrl) win.loadURL(serverUrl);
  else win.loadFile(path.join(__dirname, "setup.html"));
}

async function askServerUrl() {
  const current = readConfig().serverUrl ?? "";
  const { response } = await dialog.showMessageBox(win, {
    type: "question",
    buttons: ["Servidor na nuvem", "Servidor local", "Cancelar"],
    defaultId: 0,
    cancelId: 2,
    message: "Onde está o servidor do ROI Max?",
    detail: current ? `Atual: ${current}` : "Ainda não configurado.",
  });
  if (response === 2) return;

  if (response === 1) {
    writeConfig({ serverUrl: "http://localhost:8000" });
    load();
    return;
  }
  // a nuvem exige digitar a URL, e o Electron não tem caixa de texto nativa:
  // a página de configuração faz esse papel
  win.loadFile(path.join(__dirname, "setup.html"));
}

function buildMenu() {
  Menu.setApplicationMenu(Menu.buildFromTemplate([
    { role: "appMenu" },
    {
      label: "Arquivo",
      submenu: [
        { label: "Configurar servidor…", accelerator: "Cmd+,", click: askServerUrl },
        { type: "separator" },
        { label: "Recarregar", accelerator: "Cmd+R", click: () => win.reload() },
        {
          // Depois de um deploy, o index.html em cache aponta para arquivos
          // que já não existem e a janela fica em branco. Este é o botão de
          // emergência para isso.
          label: "Recarregar ignorando cache",
          accelerator: "Cmd+Shift+R",
          click: () => win.webContents.reloadIgnoringCache(),
        },
        { type: "separator" },
        { role: "close" },
      ],
    },
    { role: "editMenu" },
    {
      label: "Exibir",
      submenu: [
        { role: "resetZoom" }, { role: "zoomIn" }, { role: "zoomOut" },
        { type: "separator" }, { role: "togglefullscreen" },
        { type: "separator" }, { role: "toggleDevTools" },
      ],
    },
    { role: "windowMenu" },
  ]));
}

function createWindow() {
  const { bounds } = readConfig();
  win = new BrowserWindow({
    width: bounds?.width ?? 1180,
    height: bounds?.height ?? 820,
    x: bounds?.x,
    y: bounds?.y,
    minWidth: 380,          // continua utilizável estreito, como no celular
    minHeight: 480,
    titleBarStyle: "hiddenInset",
    backgroundColor: "#0b0f14",
    show: false,
    webPreferences: { contextIsolation: true, nodeIntegration: false },
  });

  win.once("ready-to-show", () => win.show());

  // Tela em branco depois de um deploy é quase sempre index.html velho em
  // cache. Se o app carregar e não renderizar nada, recarrega ignorando o
  // cache uma vez, sozinho — em vez de deixar a janela branca sem explicação.
  win.webContents.on("did-finish-load", async () => {
    if (!readConfig().serverUrl) return;
    try {
      const vazio = await win.webContents.executeJavaScript(
        "(document.getElementById('root')?.innerHTML?.length ?? 0) === 0"
      );
      if (vazio && !win.__jaRecarregou) {
        win.__jaRecarregou = true;
        win.webContents.reloadIgnoringCache();
      }
    } catch {
      /* página de configuração não tem #root: nada a fazer */
    }
  });
  win.on("close", () => writeConfig({ bounds: win.getBounds() }));

  // Qualquer link para fora (Betfair, the-odds-api) abre no navegador padrão.
  // Dentro do app ele abriria sem a sessão logada — inútil na prática.
  const externo = (url) => {
    const alvo = readConfig().serverUrl ?? "";
    return !url.startsWith(alvo) && !url.startsWith("file://");
  };
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (externo(url)) shell.openExternal(url);
    return { action: "deny" };
  });
  win.webContents.on("will-navigate", (e, url) => {
    if (externo(url)) {
      e.preventDefault();
      shell.openExternal(url);
    }
  });

  win.webContents.on("did-fail-load", (_e, code, desc) => {
    if (code === -3) return; // navegação abortada, não é falha real
    dialog.showMessageBox(win, {
      type: "error",
      message: "Não consegui falar com o servidor",
      detail: `${desc}\n\nConfira em Arquivo → Configurar servidor.`,
    }).then(() => win.loadFile(path.join(__dirname, "setup.html")));
  });

  load();
}

// a página de configuração devolve a URL por aqui
app.on("web-contents-created", (_e, contents) => {
  contents.on("console-message", (_ev, _lvl, message) => {
    const m = /^ROIMAX_SET_URL:(.+)$/.exec(message);
    if (m) {
      writeConfig({ serverUrl: m[1].trim().replace(/\/+$/, "") });
      load();
    }
  });
});

nativeTheme.themeSource = "dark";
app.whenReady().then(() => {
  buildMenu();
  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});
app.on("window-all-closed", () => process.platform !== "darwin" && app.quit());
