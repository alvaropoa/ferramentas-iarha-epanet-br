# -*- coding: utf-8 -*-
"""
Ferramenta 8 — Imagem de Fundo  (ALTERA o projeto: seção [BACKDROP])
Uso (parâmetros no EPANET):  "<pasta>\\08_imagem_fundo.py" $INPFILE
Marque "Atualizar o Epanet após finalizar o programa" para o fundo aparecer.

Calcula a área da rede pelas coordenadas do INP (nós e vértices), baixa uma imagem
de satélite ou de mapa já no sistema de coordenadas da rede, grava em BMP (formato
aceito pelo EPANET como fundo) e escreve a seção [BACKDROP] com as dimensões exatas
da imagem. As coordenadas da rede precisam estar georreferenciadas (UTM ou graus).

Uso sem janela (testes):
  08_imagem_fundo.py arquivo.inp EPSG [satelite|ruas|topografico|cinza] [LADO_MAX] [MARGEM_%]
  08_imagem_fundo.py arquivo.inp --remover
"""
import os, sys, json, math, struct, tempfile, subprocess, urllib.request, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from epanet_comum import Inp, arg_arquivo, avisar

PASTA = os.path.dirname(os.path.abspath(__file__))
ARQ_CFG = os.path.join(PASTA, "config_fundo.json")

# Serviços de mapa da Esri (ArcGIS Online). A operação "export" devolve a imagem já
# reprojetada para o sistema pedido, então não é preciso recortar nem reprojetar aqui.
SERVIDOR = os.environ.get("IARHA_FUNDO_URL", "https://services.arcgisonline.com/ArcGIS/rest/services")
BASES = {
    "satelite":    ("Satélite (Esri World Imagery)", "World_Imagery",
                    "Esri, Maxar, Earthstar Geographics e comunidade de usuários GIS"),
    "ruas":        ("Ruas (Esri World Street Map)", "World_Street_Map",
                    "Esri, HERE, Garmin, USGS, OpenStreetMap e comunidade de usuários GIS"),
    "topografico": ("Topográfico (Esri World Topo Map)", "World_Topo_Map",
                    "Esri, HERE, Garmin, USGS, OpenStreetMap e comunidade de usuários GIS"),
    "cinza":       ("Cinza claro (Esri Light Gray Canvas)", "Canvas/World_Light_Gray_Base",
                    "Esri, HERE, Garmin, OpenStreetMap e comunidade de usuários GIS"),
}

SRC = ([(31978 + i, "SIRGAS 2000 / UTM zona %dS" % (18 + i)) for i in range(8)]
       + [(31972 + i, "SIRGAS 2000 / UTM zona %dN" % (18 + i)) for i in range(5)]
       + [(32718 + i, "WGS 84 / UTM zona %dS" % (18 + i)) for i in range(8)]
       + [(4674, "SIRGAS 2000 geográficas (graus)"), (4326, "WGS 84 geográficas (graus)")])
NOME_SRC = dict(SRC)
GEOGRAFICOS = (4326, 4674)
LADOS = [1024, 2048, 3072, 4096]          # 4096 é o máximo aceito pelo serviço


# ------------------------------------------------------------ geometria -----

def extensao(inp):
    xs, ys = [], []
    for sec in ("COORDINATES", "VERTICES"):
        for tok in inp.tabela(sec):
            try:
                xs.append(float(tok[1])); ys.append(float(tok[2]))
            except (IndexError, ValueError):
                pass
    if not xs:
        raise ValueError("A rede não tem coordenadas ([COORDINATES] vazia).")
    return min(xs), min(ys), max(xs), max(ys), len(inp.tabela("COORDINATES"))


def palpite_epsg(ext, salvo):
    """Graus quando as coordenadas cabem em lon/lat; senão o último sistema usado."""
    x0, y0, x1, y1, _ = ext
    if -180 <= x0 <= x1 <= 180 and -90 <= y0 <= y1 <= 90 and (x1 - x0) < 5:
        return salvo if salvo in GEOGRAFICOS else 4674
    return salvo if salvo and salvo not in GEOGRAFICOS else 31982


def checar_coerencia(ext, epsg):
    """Mensagem de alerta quando as coordenadas não combinam com o sistema escolhido."""
    x0, y0, x1, y1, _ = ext
    if epsg in GEOGRAFICOS:
        if not (-180 <= x0 <= x1 <= 180 and -90 <= y0 <= y1 <= 90):
            return "As coordenadas não estão em graus (longitude/latitude)."
        return ""
    if x1 - x0 < 1 and y1 - y0 < 1:
        return "A rede parece estar em graus, mas o sistema escolhido é UTM."
    if not (100000 <= x0 and x1 <= 900000) or not (0 <= y0 and y1 <= 10000000):
        return ("As coordenadas (X %.0f a %.0f, Y %.0f a %.0f) não parecem UTM. "
                "A rede pode não estar georreferenciada." % (x0, x1, y0, y1))
    return ""


def enquadrar(ext, margem_pct, lado_max):
    """Caixa com margem e tamanho em pixels com pixel quadrado (proporção exata)."""
    x0, y0, x1, y1, _ = ext
    dx, dy = max(x1 - x0, 1e-9), max(y1 - y0, 1e-9)
    dx, dy = max(dx, dy * 0.05), max(dy, dx * 0.05)      # rede em linha reta
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    dx *= 1 + 2 * margem_pct / 100.0
    dy *= 1 + 2 * margem_pct / 100.0
    px = max(dx, dy) / float(lado_max)
    w, h = max(1, int(math.ceil(dx / px))), max(1, int(math.ceil(dy / px)))
    return (cx - w * px / 2, cy - h * px / 2, cx + w * px / 2, cy + h * px / 2), w, h, px


# ------------------------------------------------------------- download -----

def _get(url, timeout=120):
    req = urllib.request.Request(url, headers={"User-Agent": "Ferramentas-IARHA-EPANET-Br/1.1"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _erro_servico(dados):
    try:
        e = json.loads(dados.decode("utf-8", "replace")).get("error", {})
        return "%s %s" % (e.get("message", ""), " ".join(e.get("details", []) or []))
    except Exception:
        return dados[:200].decode("latin-1", "replace")


def _png_para_bmp(png, destino):
    """Plano B: o Windows converte PNG em BMP (System.Drawing), sem pacotes Python."""
    tmp = os.path.join(tempfile.gettempdir(), "iarha_fundo.png")
    with open(tmp, "wb") as f:
        f.write(png)
    ps = ("Add-Type -AssemblyName System.Drawing;"
          "$i=[System.Drawing.Image]::FromFile('%s');"
          "$i.Save('%s',[System.Drawing.Imaging.ImageFormat]::Bmp);$i.Dispose()"
          % (tmp.replace("'", "''"), destino.replace("'", "''")))
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
                   check=True, capture_output=True, timeout=120,
                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def baixar(base, caixa, epsg, w, h, destino):
    """Baixa a imagem para a caixa exata. Devolve a caixa que o servidor realmente usou."""
    servico = BASES[base][1]
    params = {"bbox": "%.6f,%.6f,%.6f,%.6f" % caixa, "bboxSR": epsg, "imageSR": epsg,
              "size": "%d,%d" % (w, h), "dpi": 96, "transparent": "false"}
    url = "%s/%s/MapServer/export?" % (SERVIDOR.rstrip("/"), servico)
    erros = []
    # 1º BMP direto; 2º PNG convertido pelo Windows
    for fmt in ("bmp", "png24"):
        q = dict(params, format=fmt, f="json")
        caixa_real = caixa
        try:
            info = json.loads(_get(url + urllib.parse.urlencode(q)).decode("utf-8"))
            if "error" in info:
                raise RuntimeError(_erro_servico(json.dumps(info).encode()))
            dados = _get(info["href"])
            e = info.get("extent") or {}
            if all(k in e for k in ("xmin", "ymin", "xmax", "ymax")):
                caixa_real = (e["xmin"], e["ymin"], e["xmax"], e["ymax"])
        except Exception as ex:                     # alguns servidores só respondem f=image
            erros.append("%s/json: %s" % (fmt, ex))
            try:
                dados = _get(url + urllib.parse.urlencode(dict(params, format=fmt, f="image")))
            except Exception as ex2:
                erros.append("%s/image: %s" % (fmt, ex2)); continue
        if fmt == "bmp" and dados[:2] == b"BM":
            with open(destino, "wb") as f:
                f.write(dados)
            return caixa_real
        if fmt != "bmp" and dados[:8] == b"\x89PNG\r\n\x1a\n":
            try:
                _png_para_bmp(dados, destino)
                return caixa_real
            except Exception as ex:
                erros.append("conversão PNG→BMP: %s" % ex); continue
        erros.append("%s: resposta inesperada (%s)" % (fmt, _erro_servico(dados)))
    raise RuntimeError("Não consegui baixar a imagem.\n\n" + "\n".join(erros[-4:]))


def dimensoes_bmp(caminho):
    with open(caminho, "rb") as f:
        cab = f.read(26)
    return struct.unpack("<i", cab[18:22])[0], abs(struct.unpack("<i", cab[22:26])[0])


# ------------------------------------------------------------ [BACKDROP] -----

def _faixa_secao(inp, nome):
    ini = None
    for i, ln in enumerate(inp.linhas):
        s = ln.strip().upper()
        if s.startswith("["):
            if ini is not None:
                return ini, i
            if s.startswith("[%s]" % nome):
                ini = i
    return (ini, len(inp.linhas)) if ini is not None else (None, None)


def gravar_backdrop(inp, caixa, unidade, arquivo):
    """Reescreve a seção [BACKDROP]; cria a seção antes de [END] se não existir."""
    novas = [" DIMENSIONS     \t%.3f\t%.3f\t%.3f\t%.3f" % caixa,
             " UNITS          \t%s" % unidade]
    if arquivo:
        novas.append(' FILE           \t"%s"' % arquivo)
    novas.append(" OFFSET         \t0.00\t0.00")
    ini, fim = _faixa_secao(inp, "BACKDROP")
    if ini is None:
        pos = _faixa_secao(inp, "END")[0]
        pos = len(inp.linhas) if pos is None else pos
        inp.linhas[pos:pos] = ["[BACKDROP]"] + novas + [""]
    else:
        coment = [l for l in inp.linhas[ini + 1:fim] if l.strip().startswith(";")]
        inp.linhas[ini + 1:fim] = coment + novas + [""]
    inp._indexar()


def remover_backdrop(inp):
    ini, fim = _faixa_secao(inp, "BACKDROP")
    if ini is None:
        return False
    antes = len(inp.linhas)
    inp.linhas[ini + 1:fim] = [l for l in inp.linhas[ini + 1:fim]
                               if not l.strip().upper().startswith("FILE")]
    inp._indexar()
    return len(inp.linhas) != antes


def pasta_imagem(inp_caminho):
    """Ao lado do INP; se o INP estiver na pasta temporária, em Documentos\\EPANET_Fundos."""
    pasta = os.path.dirname(os.path.abspath(inp_caminho))
    tmp = os.path.normcase(os.path.abspath(tempfile.gettempdir()))
    if os.path.normcase(pasta).startswith(tmp) or not os.access(pasta, os.W_OK):
        pasta = os.path.join(os.path.expanduser("~"), "Documents", "EPANET_Fundos")
        os.makedirs(pasta, exist_ok=True)
    return pasta


def aplicar(inp, epsg, base, lado, margem):
    ext = extensao(inp)
    caixa, w, h, px = enquadrar(ext, margem, lado)
    # O EPANET passa um INP temporário de nome fixo: a área entra no nome para que
    # projetos diferentes não sobrescrevam a imagem um do outro.
    import hashlib
    nome = os.path.splitext(os.path.basename(inp.caminho))[0]
    marca = hashlib.md5(("%d %.6f %.6f %.6f %.6f" % ((epsg,) + caixa)).encode()).hexdigest()[:8]
    destino = os.path.join(pasta_imagem(inp.caminho), "%s_fundo_%s_%s.bmp" % (nome, base, marca))
    caixa = baixar(base, caixa, epsg, w, h, destino)
    wi, hi = dimensoes_bmp(destino)
    gravar_backdrop(inp, caixa, "DEGREES" if epsg in GEOGRAFICOS else "METERS", destino)
    inp.salvar()
    return destino, wi, hi, (caixa[2] - caixa[0]) / max(wi, 1)


# --------------------------------------------------------------- config -----

def ler_cfg():
    try:
        with open(ARQ_CFG, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def salvar_cfg(c):
    try:
        with open(ARQ_CFG, "w", encoding="utf-8") as f:
            json.dump(c, f, ensure_ascii=False, indent=1)
    except Exception:
        pass


# ---------------------------------------------------------------- janela -----

def janela(inp):
    import tkinter as tk
    from tkinter import ttk, messagebox
    ext = extensao(inp)
    cfg = ler_cfg()
    epsg0 = palpite_epsg(ext, cfg.get("epsg"))
    rot_src = ["%d — %s" % (c, n) for c, n in SRC]
    r = tk.Tk()
    r.title("Imagem de Fundo — EPANET 2.2 Brasil")
    r.resizable(False, False)
    f = ttk.Frame(r, padding=14); f.grid()
    x0, y0, x1, y1, nn = ext
    c = lambda v: ("%.0f" if abs(v) >= 1000 else "%.6g") % v
    ttk.Label(f, text="%d nós · área das coordenadas: X %s a %s · Y %s a %s"
              % (nn, c(x0), c(x1), c(y0), c(y1))).grid(columnspan=3, sticky="w", pady=(0, 10))

    v_src = tk.StringVar(value="%d — %s" % (epsg0, NOME_SRC.get(epsg0, "EPSG %d" % epsg0)))
    v_base = tk.StringVar(value=BASES[cfg.get("base", "satelite")][0])
    v_lado = tk.StringVar(value=str(cfg.get("lado", 2048)))
    v_marg = tk.StringVar(value=str(cfg.get("margem", 5)))
    v_info, v_alerta = tk.StringVar(), tk.StringVar()

    linhas = [("Sistema de coordenadas da rede", ttk.Combobox(f, textvariable=v_src, values=rot_src, width=46)),
              ("Mapa de fundo", ttk.Combobox(f, textvariable=v_base, state="readonly", width=46,
                                             values=[b[0] for b in BASES.values()])),
              ("Lado maior da imagem (pixels)", ttk.Combobox(f, textvariable=v_lado, width=10,
                                                              values=[str(l) for l in LADOS])),
              ("Margem em volta da rede (%)", ttk.Entry(f, textvariable=v_marg, width=10))]
    for i, (rot, wid) in enumerate(linhas, start=1):
        ttk.Label(f, text=rot).grid(row=i, column=0, sticky="w", padx=(0, 10))
        wid.grid(row=i, column=1, sticky="w", pady=3)
    ttk.Label(f, text="Outro sistema: digite o código EPSG.", foreground="#666").grid(
        row=5, column=1, sticky="w")
    ttk.Label(f, textvariable=v_info, foreground="#1F3864").grid(row=6, columnspan=3, sticky="w", pady=(10, 0))
    ttk.Label(f, textvariable=v_alerta, foreground="#B00020", wraplength=520).grid(
        row=7, columnspan=3, sticky="w")
    v_status = tk.StringVar()
    ttk.Label(f, textvariable=v_status).grid(row=9, columnspan=3, sticky="w", pady=(6, 0))

    def ler():
        import re
        m = re.search(r"\d{4,6}", v_src.get())
        if not m:
            raise ValueError("Escolha o sistema de coordenadas ou digite o código EPSG.")
        base = [k for k, b in BASES.items() if b[0] == v_base.get()][0]
        lado = int(float(v_lado.get().replace(",", ".")))
        if not 256 <= lado <= 4096:
            raise ValueError("O lado maior deve ficar entre 256 e 4096 pixels.")
        marg = float(v_marg.get().replace(",", "."))
        return int(m.group()), base, lado, marg

    def atualizar(*_):
        try:
            epsg, base, lado, marg = ler()
        except Exception as e:
            v_info.set(""); v_alerta.set(str(e)); return
        caixa, w, h, px = enquadrar(ext, marg, lado)
        un = "graus" if epsg in GEOGRAFICOS else "m"
        v_info.set("Imagem de %d × %d pixels · %.3g %s por pixel · arquivo de %.1f MB"
                   % (w, h, px, un, w * h * 3 / 1e6))
        v_alerta.set(checar_coerencia(ext, epsg))

    for v in (v_src, v_base, v_lado, v_marg):
        v.trace_add("write", atualizar)
    atualizar()

    def executar():
        try:
            epsg, base, lado, marg = ler()
        except Exception as e:
            messagebox.showerror("Valor inválido", str(e)); return
        alerta = checar_coerencia(ext, epsg)
        if alerta and not messagebox.askyesno("Conferir coordenadas", alerta + "\n\nBaixar mesmo assim?"):
            return
        salvar_cfg({"epsg": epsg, "base": base, "lado": lado, "margem": marg})
        v_status.set("Baixando a imagem… pode levar alguns segundos.")
        r.config(cursor="watch"); r.update()
        try:
            destino, wi, hi, px = aplicar(inp, epsg, base, lado, marg)
        except Exception as e:
            r.config(cursor=""); v_status.set("")
            messagebox.showerror("Imagem de Fundo — erro", "%s\n\nConfira a conexão com a internet "
                                 "(proxy da empresa) e o sistema de coordenadas." % e); return
        r.config(cursor="")
        messagebox.showinfo("Imagem de Fundo", "Fundo aplicado: %d × %d pixels.\n\nImagem: %s\n"
                            "Fonte: %s.\n\nO EPANET vai recarregar o projeto com o fundo. Para "
                            "esconder ou mostrar, use o comando de fundo (Backdrop) do menu Exibir."
                            % (wi, hi, destino, BASES[base][2]))
        r.destroy()

    def remover():
        if remover_backdrop(inp):
            inp.salvar()
            messagebox.showinfo("Imagem de Fundo", "Fundo removido do projeto.")
        else:
            messagebox.showinfo("Imagem de Fundo", "O projeto não tem imagem de fundo.")
        r.destroy()

    b = ttk.Frame(f); b.grid(row=8, columnspan=3, pady=(14, 0), sticky="ew")
    ttk.Button(b, text="Remover fundo", command=remover).pack(side="left")
    ttk.Button(b, text="Cancelar", command=r.destroy).pack(side="right", padx=4)
    ttk.Button(b, text="Baixar e aplicar", command=executar).pack(side="right")
    r.mainloop()


def main():
    inp = Inp(arg_arquivo(1, "$INPFILE"))
    if len(sys.argv) >= 3 and sys.argv[2] == "--remover":
        ok = remover_backdrop(inp)
        if ok:
            inp.salvar()
        print("Fundo removido." if ok else "Sem fundo.")
    elif len(sys.argv) >= 3:
        epsg = int(sys.argv[2])
        base = sys.argv[3] if len(sys.argv) > 3 else "satelite"
        lado = int(sys.argv[4]) if len(sys.argv) > 4 else 2048
        marg = float(sys.argv[5]) if len(sys.argv) > 5 else 5.0
        destino, wi, hi, px = aplicar(inp, epsg, base, lado, marg)
        print("%s  %dx%d  %.3g por pixel" % (destino, wi, hi, px))
    else:
        janela(inp)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        import traceback
        avisar("Imagem de Fundo — erro", "%s\n\n%s" % (e, traceback.format_exc()[-600:]), erro=True)
