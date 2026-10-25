# -*- coding: utf-8 -*-
"""
epanet_comum.py — utilitários compartilhados pelas ferramentas de demonstração
para o menu "Ferramentas" do EPANET 2.2 Brasil.

Somente biblioteca padrão do Python (3.8+). Nada para instalar.
"""
import os
import sys
import struct
import tempfile
import webbrowser
import datetime
import html

# ---------------------------------------------------------------- INP -----

def ler_texto(caminho):
    """Lê o arquivo tentando UTF-8 e caindo para cp1252 (padrão do EPANET no Windows)."""
    with open(caminho, "rb") as f:
        bruto = f.read()
    if bruto.startswith(b"\xef\xbb\xbf"):
        return bruto[3:].decode("utf-8", errors="replace"), "utf-8-sig"
    for enc in ("utf-8", "cp1252", "latin-1"):   # gravação volta na mesma codificação, sem BOM
        try:
            return bruto.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return bruto.decode("latin-1", errors="replace"), "latin-1"


class Inp:
    """INP mantido como lista de linhas; seções indexadas por nome (sem colchetes, maiúsculas)."""

    def __init__(self, caminho):
        self.caminho = caminho
        texto, self.encoding = ler_texto(caminho)
        self.nova_linha = "\r\n" if "\r\n" in texto else "\n"
        self.linhas = texto.splitlines()
        self._indexar()

    def _indexar(self):
        self.secoes = {}
        atual = None
        for i, ln in enumerate(self.linhas):
            s = ln.strip()
            if s.startswith("[") and "]" in s:
                atual = s[1:s.index("]")].strip().upper()
                self.secoes.setdefault(atual, [])
                continue
            if atual is None:
                continue
            dado = s.split(";", 1)[0].strip()
            if dado:
                self.secoes[atual].append((i, dado.split()))

    def tabela(self, secao):
        """Lista de listas de tokens da seção."""
        return [tok for _, tok in self.secoes.get(secao.upper(), [])]

    def opcao(self, chave, padrao=None):
        chave = chave.upper()
        for tok in self.tabela("OPTIONS"):
            if tok and tok[0].upper() == chave and len(tok) > 1:
                return " ".join(tok[1:])
        return padrao

    def unidades_si(self):
        u = (self.opcao("UNITS", "GPM") or "GPM").upper()
        return u in ("LPS", "LPM", "MLD", "CMH", "CMD", "CMS")

    def formula(self):
        f = (self.opcao("HEADLOSS", "H-W") or "H-W").upper()
        return {"H-W": "H-W", "D-W": "D-W", "C-M": "C-M"}.get(f, f)

    def salvar(self, caminho=None, backup=True):
        caminho = caminho or self.caminho
        if backup and os.path.exists(caminho):
            bak = caminho + ".bak"
            with open(caminho, "rb") as a, open(bak, "wb") as b:
                b.write(a.read())
        with open(caminho, "w", encoding=self.encoding, newline="") as f:
            f.write(self.nova_linha.join(self.linhas) + self.nova_linha)


def substituir_campo(linha, indice_campo, novo_valor):
    """Troca o n-ésimo campo de uma linha de dados preservando o comentário (;...)."""
    dado, sep, coment = linha.partition(";")
    campos = dado.split()
    campos[indice_campo] = novo_valor
    nova = "\t".join(campos)
    if sep:
        nova += "\t;" + coment
    return nova


# ---------------------------------------------------- binário .out -----

TIPOS_LINK = {0: "Válvula retenção", 1: "Tubo", 2: "Bomba"}
UNID_PRESSAO = {0: "psi", 1: "kPa", 2: "mca", 3: "bar", 4: "ft"}
UNID_VAZAO = {0: "cfs", 1: "gpm", 2: "mgd", 3: "imgd", 4: "afd",
              5: "L/s", 6: "L/min", 7: "ML/d", 8: "m³/h", 9: "m³/d", 10: "m³/s"}
MAGICO = 516114521


class SaidaBinaria:
    """Leitor do arquivo binário de resultados do EPANET 2.x (formato documentado no Toolkit)."""

    def __init__(self, caminho):
        with open(caminho, "rb") as f:
            self.b = f.read()
        b = self.b
        if len(b) < 912:
            raise ValueError("Arquivo de saída vazio ou incompleto — rode a simulação antes.")
        cab = struct.unpack_from("<15i", b, 0)
        if cab[0] != MAGICO:
            raise ValueError("Arquivo não é uma saída binária do EPANET.")
        (_, self.versao, self.nn, self.nt, self.nl, self.np, self.nv,
         _, _, self.u_vazao, self.u_pressao, _, self.t_ini, self.t_passo, self.duracao) = cab
        ep = struct.unpack_from("<4f3i", b, len(b) - 28)
        self.nperiodos, self.aviso = ep[4], ep[5]
        if ep[6] != MAGICO:
            raise ValueError("Saída binária truncada — a simulação terminou com erro?")

        off = 884
        self.nos = [self._id(off + 32 * i) for i in range(self.nn)]; off += 32 * self.nn
        self.links = [self._id(off + 32 * i) for i in range(self.nl)]; off += 32 * self.nl
        self.link_ini = struct.unpack_from("<%di" % self.nl, b, off); off += 4 * self.nl
        self.link_fim = struct.unpack_from("<%di" % self.nl, b, off); off += 4 * self.nl
        self.link_tipo = struct.unpack_from("<%di" % self.nl, b, off); off += 4 * self.nl
        tanques = struct.unpack_from("<%di" % self.nt, b, off); off += 4 * self.nt
        areas = struct.unpack_from("<%df" % self.nt, b, off); off += 4 * self.nt
        self.idx_tanques = {t - 1 for t, a in zip(tanques, areas) if a > 0}   # RNV (área > 0)
        self.cotas = struct.unpack_from("<%df" % self.nn, b, off); off += 4 * self.nn
        self.comprimentos = struct.unpack_from("<%df" % self.nl, b, off); off += 4 * self.nl
        self.diametros = struct.unpack_from("<%df" % self.nl, b, off); off += 4 * self.nl
        self.idx_fontes = {t - 1 for t in tanques}          # reservatórios e tanques
        off += 28 * self.np + 4                              # seção de energia
        self.off_din = off
        self.tam_periodo = 16 * self.nn + 32 * self.nl

    def _id(self, off):
        return self.b[off:off + 32].split(b"\0", 1)[0].decode("latin-1").strip()

    def periodo(self, k):
        """Retorna (pressoes[nn], velocidades[nl], vazoes[nl], status[nl]) do período k."""
        o = self.off_din + k * self.tam_periodo
        nn, nl = self.nn, self.nl
        pres = struct.unpack_from("<%df" % nn, self.b, o + 8 * nn)
        ol = o + 16 * nn
        vaz = struct.unpack_from("<%df" % nl, self.b, ol)
        vel = struct.unpack_from("<%df" % nl, self.b, ol + 4 * nl)
        sta = struct.unpack_from("<%df" % nl, self.b, ol + 16 * nl)
        return pres, vel, vaz, sta

    def completo(self, k):
        """Todos os resultados do período k: dem, carga, pres (nós); vaz, vel, perda, sta (trechos).
        Perda = perda de carga unitária (por 1000 unidades de comprimento) nos tubos."""
        o = self.off_din + k * self.tam_periodo
        nn, nl = self.nn, self.nl
        v = lambda off, n: struct.unpack_from("<%df" % n, self.b, off)
        ol = o + 16 * nn
        return {"dem": v(o, nn), "carga": v(o + 4 * nn, nn), "pres": v(o + 8 * nn, nn),
                "vaz": v(ol, nl), "vel": v(ol + 4 * nl, nl), "perda": v(ol + 8 * nl, nl), "sta": v(ol + 16 * nl, nl)}

    def demandas(self, k):
        """Demanda em cada nó no período k (unidade de vazão do projeto)."""
        return struct.unpack_from("<%df" % self.nn, self.b, self.off_din + k * self.tam_periodo)

    def hora(self, k):
        s = self.t_ini + k * self.t_passo
        return "%d:%02d" % (s // 3600, (s % 3600) // 60)


# ------------------------------------------- simulação com o EPANET Br -----
# O EPANET 2.2 Brasil não oferece $OUTFILE no menu Ferramentas. As ferramentas que
# precisam de resultados recebem $INPFILE e simulam com o runepanet.exe que vem
# na pasta do próprio EPANET Br (mesmo motor Epanet2.dll da interface).

def _candidatos_runepanet():
    env = os.environ.get("IARHA_RUNEPANET")
    if env:
        yield env
    aqui = os.path.dirname(os.path.abspath(__file__))
    yield os.path.join(aqui, "runepanet.exe")
    for pf in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"),
               r"C:\Program Files (x86)", r"C:\Program Files"):
        if pf:
            for d in ("Epanet 2.2 Brasil", "EPANET 2.2 Brasil", "EPANET 2.2"):
                yield os.path.join(pf, d, "runepanet.exe")


def simular(inp):
    """Simula o INP com o runepanet.exe do EPANET Br e devolve o caminho do .out."""
    import shutil
    import subprocess
    exe = next((c for c in _candidatos_runepanet() if os.path.isfile(c)), None)
    if not exe:
        raise ValueError("Não encontrei o runepanet.exe do EPANET 2.2 Brasil.\n\n"
                         "Copie o arquivo\n   C:\\Program Files (x86)\\Epanet 2.2 Brasil\\runepanet.exe\n"
                         "para a pasta das ferramentas e rode de novo.")
    pasta = os.path.join(tempfile.gettempdir(), "IARHA_simulacao")
    os.makedirs(pasta, exist_ok=True)
    i, r, o = (os.path.join(pasta, "modelo." + e) for e in ("inp", "rpt", "out"))
    for f in (r, o):
        if os.path.exists(f):
            os.remove(f)
    shutil.copyfile(inp, i)   # nome simples: evita acentos e espaços no motor
    sem_janela = 0x08000000 if os.name == "nt" else 0   # CREATE_NO_WINDOW
    subprocess.run([exe, i, r, o], cwd=os.path.dirname(exe), creationflags=sem_janela,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3600)
    try:
        with open(o, "rb") as f:
            f.seek(-4, 2)
            ok = struct.unpack("<i", f.read(4))[0] == MAGICO
    except OSError:
        ok = False
    if not ok:
        detalhe = ""
        if os.path.exists(r):
            linhas = [l.strip() for l in ler_texto(r)[0].splitlines() if l.strip()]
            erros = [l for l in linhas if "rror" in l or "ERRO" in l.upper()]
            detalhe = "\n".join((erros or linhas)[:8])
        raise ValueError("A simulação não terminou.\n\n" + (detalhe or "Sem relatório do motor.") +
                         "\n\nRelatório completo em:\n" + r)
    return o


def resultados_de(arquivo):
    """Aceita um INP (simula) ou um .out já pronto (usa direto)."""
    with open(arquivo, "rb") as f:
        cab = f.read(4)
    if len(cab) == 4 and struct.unpack("<i", cab)[0] == MAGICO:
        return arquivo
    return simular(arquivo)


# ------------------------------------------------------ relatório HTML -----

CSS = """
:root{--bg:#f7f8fa;--card:#fff;--tx:#1d2733;--mut:#5d6b7a;--bd:#dfe4ea;--ac:#0b6e99;
--ok:#1f7a4d;--warn:#b26a00;--err:#b42318}
@media (prefers-color-scheme:dark){:root{--bg:#12161b;--card:#1a2027;--tx:#e6ebf0;--mut:#9aa7b4;
--bd:#2c353f;--ac:#4fb3e0;--ok:#4cc38a;--warn:#f0a83a;--err:#f2716a}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--tx);
font:15px/1.5 "Segoe UI",system-ui,sans-serif}main{max-width:1100px;margin:0 auto;padding:24px 16px}
h1{font-size:22px;margin:0 0 4px}h2{font-size:17px;margin:28px 0 10px}.sub{color:var(--mut);margin:0 0 20px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px}
.kpi{background:var(--card);border:1px solid var(--bd);border-radius:10px;padding:12px 14px}
.kpi b{display:block;font-size:22px}.kpi span{color:var(--mut);font-size:13px}
table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--bd);border-radius:10px;overflow:hidden}
th,td{padding:7px 10px;border-bottom:1px solid var(--bd);text-align:left;font-variant-numeric:tabular-nums}
th{font-size:13px;color:var(--mut);font-weight:600}td.n{text-align:right}
.tag{display:inline-block;padding:1px 8px;border-radius:99px;font-size:12px;font-weight:600;border:1px solid}
.ok{color:var(--ok)}.warn{color:var(--warn)}.err{color:var(--err)}
.bar{height:8px;background:var(--ac);border-radius:4px}
footer{color:var(--mut);font-size:12px;margin-top:32px}
"""


def esc(x):
    return html.escape(str(x))


def tabela_html(cab, linhas, numericas=()):
    h = "<table><thead><tr>" + "".join(
        ("<th style='text-align:right'>%s</th>" if i in numericas else "<th>%s</th>") % esc(c)
        for i, c in enumerate(cab)) + "</tr></thead><tbody>"
    for ln in linhas:
        h += "<tr>" + "".join(
            '<td class="n">%s</td>' % c if i in numericas else "<td>%s</td>" % c
            for i, c in enumerate(ln)) + "</tr>"
    return h + "</tbody></table>"


def gravar_relatorio(titulo, subtitulo, corpo, nome_arquivo, pasta=None, abrir=True):
    pasta = pasta or tempfile.gettempdir()
    caminho = os.path.join(pasta, nome_arquivo)
    agora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    doc = ("<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'>"
           "<meta name='viewport' content='width=device-width,initial-scale=1'>"
           "<title>%s</title><style>%s</style></head><body><main><h1>%s</h1><p class='sub'>%s</p>%s"
           "<footer>Gerado em %s · Ferramenta de demonstração para EPANET 2.2 Brasil</footer>"
           "</main></body></html>") % (esc(titulo), CSS, esc(titulo), esc(subtitulo), corpo, agora)
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(doc)
    if abrir:
        webbrowser.open("file:///" + os.path.abspath(caminho).replace("\\", "/"))
    return caminho


def avisar(titulo, msg, erro=False):
    """Caixa de mensagem se houver tkinter; senão imprime."""
    try:
        import tkinter as tk
        from tkinter import messagebox
        r = tk.Tk(); r.withdraw()
        (messagebox.showerror if erro else messagebox.showinfo)(titulo, msg)
        r.destroy()
    except Exception:
        print(("ERRO: " if erro else "") + titulo + "\n" + msg)


def arg_arquivo(pos, descricao):
    if len(sys.argv) <= pos or not sys.argv[pos].strip():
        avisar("Parâmetro ausente", "Faltou o parâmetro %s.\nVerifique a configuração da ferramenta "
               "(Ferramentas > Configurar)." % descricao, erro=True)
        sys.exit(1)
    # O EPANET pode passar o caminho sem aspas: "C:\Users\Alvaro Ribeiro\x.inp" chega
    # partido em vários argumentos. Remonta juntando pedaços até o arquivo existir.
    for fim in range(pos + 1, len(sys.argv) + 1):
        p = " ".join(sys.argv[pos:fim]).strip().strip('"')
        if os.path.isfile(p):
            sys.argv[pos:fim] = [p]          # demais parâmetros voltam ao lugar certo
            return p
    p = " ".join(sys.argv[pos:]).strip().strip('"')
    avisar("Arquivo não encontrado", "%s não existe:\n%s\n\nArgumentos recebidos:\n%s"
           % (descricao, p, "\n".join(sys.argv[1:])), erro=True)
    sys.exit(1)


def numeros(args, padroes):
    """Converte os parâmetros numéricos opcionais (limites, K1...). Tolera vírgula decimal e
    caracteres colados por engano ao copiar (crase, aspas); o que não for número fica no padrão."""
    import re
    vals = []
    for a in args:
        m = re.search(r"-?\d+(?:[.,]\d+)?", a)
        if m:
            vals.append(float(m.group().replace(",", ".")))
    return (vals + list(padroes)[len(vals):])[:len(padroes)]


def fmt(x, casas=2):
    return ("{:,.%df}" % casas).format(x).replace(",", "X").replace(".", ",").replace("X", ".")
