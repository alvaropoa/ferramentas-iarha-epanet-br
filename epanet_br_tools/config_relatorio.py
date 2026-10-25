# -*- coding: utf-8 -*-
"""
Configuração do Relatório de Análise da Rede (ferramenta 6).

As escolhas ficam em config_relatorio.json, na pasta das ferramentas. A janela é
aberta pela ferramenta 7 (07_configurar_relatorio.py) ou, se marcado, antes de cada
relatório. Só biblioteca padrão (tkinter vem com o Python do python.org).
"""
import copy
import json
import os
import re
import subprocess
import sys
import tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
ARQUIVO = os.path.join(AQUI, "config_relatorio.json")

PADRAO = {
    "titulo": "IARHA — Relatório de Análise da Rede",
    "subtitulo": "",
    "responsavel": "",
    "logo": "",
    "decimal": ".",
    "perguntar": False,
    "criterios": {"pmin": 10.0, "pmax": 40.0, "palta": 50.0, "vmin": 0.4, "vmax": 3.5, "jalto": 10.0, "k1": 1.2},
    "cores": {"primaria": "#00295C", "destaque": "#034EA2", "realce": "#FCAF17", "ok": "#2E9E62",
              "critico": "#E5532D", "alerta": "#E39A0F", "neutra": "#8497B0"},
    "secoes": {"topologia": True, "pressao": True, "hidraulica": True, "demandas": True, "distribuicoes": True,
               "balanco": True, "reservacao": True, "top10": True, "diagnostico": True, "mapas": True},
    "mapas": {
        "pressao": {"ativo": True, "limites": [10, 20, 30, 40, 50],
                    "cores": ["#E5532D", "#7CC48F", "#2E9E62", "#034EA2", "#FCAF17", "#E39A0F"]},
        "perda": {"ativo": True, "limites": [3, 6, 10, 15],
                  "cores": ["#2E9E62", "#8CBF3F", "#FCAF17", "#E5532D", "#A3261B"]},
        "velocidade": {"ativo": True, "limites": [0.4, 1, 2, 3.5],
                       "cores": ["#8497B0", "#6FA8DC", "#034EA2", "#FCAF17", "#E5532D"]},
        "demanda": {"ativo": True, "rampa": ["#CFE0F3", "#00295C"]},
        "elevacao": {"ativo": True, "rampa": ["#BCCDE3", "#00295C"]},
        "diametro": {"ativo": True, "rampa": ["#B9C8DC", "#3E5A82"]},
    },
}

NOMES_SECOES = [("topologia", "Topologia da rede"), ("pressao", "Pressão — nós"), ("hidraulica", "Hidráulica — trechos"),
                ("demandas", "Demandas cadastradas"), ("distribuicoes", "Distribuições (histogramas)"),
                ("balanco", "Balanço do sistema"), ("reservacao", "Capacidade de reservação"),
                ("top10", "Tabelas Top 10"), ("diagnostico", "Diagnóstico automático"), ("mapas", "Mapas temáticos")]
NOMES_CORES = [("primaria", "Primária (textos, títulos, reservatórios)"), ("destaque", "Destaque (seções, tabelas, cards)"),
               ("realce", "Realce (sublinhados, atenção)"), ("ok", "Situação boa"), ("critico", "Situação crítica"),
               ("alerta", "Alerta forte"), ("neutra", "Neutra (textos secundários)")]
NOMES_CRITERIOS = [("pmin", "Pressão mínima", "mca"), ("pmax", "Pressão máxima (km de rede)", "mca"),
                   ("palta", "Pressão alta (alerta de VRP)", "mca"), ("vmin", "Velocidade mínima", "m/s"),
                   ("vmax", "Velocidade máxima", "m/s"), ("jalto", "Perda de carga alta", "m/km"),
                   ("k1", "K1 — dia de maior consumo", "")]
MAPAS_CLASSES = [("pressao", "Pressão", "mca"), ("perda", "Perda de carga", "m/km"), ("velocidade", "Velocidade", "m/s")]
MAPAS_RAMPA = [("demanda", "Demanda", "classes por quartis"), ("elevacao", "Elevação", "classes automáticas"),
               ("diametro", "Diâmetro", "classes de diâmetro usadas")]
HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _mesclar(base, novo):
    """Mantém a estrutura do padrão; aproveita do arquivo só chaves conhecidas e tipos compatíveis."""
    out = copy.deepcopy(base)
    for k, v in (novo or {}).items():
        if k not in out:
            continue
        if isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _mesclar(out[k], v)
        elif isinstance(out[k], list) and isinstance(v, list):
            out[k] = v
        elif isinstance(out[k], bool):
            out[k] = bool(v)
        elif isinstance(out[k], (int, float)) and isinstance(v, (int, float)):
            out[k] = float(v)
        elif isinstance(out[k], str) and isinstance(v, str):
            out[k] = v
    return out


def carregar():
    caminho = os.environ.get("IARHA_CONFIG") or ARQUIVO
    try:
        with open(caminho, encoding="utf-8") as f:
            return _mesclar(PADRAO, json.load(f))
    except (OSError, ValueError):
        return copy.deepcopy(PADRAO)


def salvar(cfg, caminho=None):
    with open(caminho or ARQUIVO, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


# ======================================================================= janela
def janela(cfg=None, botao_gerar=False):
    """Abre a janela. Retorna a configuração (dict) se o usuário salvou/gerou; None se cancelou."""
    import tkinter as tk
    from tkinter import ttk, colorchooser, filedialog, messagebox

    cfg = copy.deepcopy(cfg or carregar())
    resultado = {"cfg": None}
    r = tk.Tk()
    r.title("Configurar Relatório de Análise da Rede — IARHA")
    r.minsize(640, 520)
    try:
        r.call("tk", "scaling", r.winfo_fpixels("1i") / 72.0)
    except tk.TclError:
        pass
    est = ttk.Style(r)
    if "vista" in est.theme_names():
        est.theme_use("vista")
    est.configure("Titulo.TLabel", font=("Segoe UI", 11, "bold"))
    est.configure("Nota.TLabel", foreground="#5B6B80")

    raiz = ttk.Frame(r, padding=12); raiz.pack(fill="both", expand=True)
    ttk.Label(raiz, text="Personalize o relatório. As escolhas ficam salvas para os próximos relatórios.",
              style="Nota.TLabel").pack(anchor="w", pady=(0, 8))
    abas = ttk.Notebook(raiz); abas.pack(fill="both", expand=True)

    def amostra(pai, var):
        """Quadrado de cor + campo hex + botão de escolha, ligados à StringVar."""
        f = ttk.Frame(pai)
        q = tk.Label(f, width=3, relief="solid", bd=1, bg=var.get() if HEX.match(var.get()) else "#FFFFFF")
        q.pack(side="left", padx=(0, 6), ipady=2)
        e = ttk.Entry(f, textvariable=var, width=9); e.pack(side="left")

        def escolher():
            c = colorchooser.askcolor(color=var.get() if HEX.match(var.get()) else None, parent=r, title="Escolher cor")
            if c and c[1]:
                var.set(c[1].upper())

        def atualizar(*_):
            if HEX.match(var.get().strip()):
                q.configure(bg=var.get().strip())
        var.trace_add("write", atualizar)
        q.bind("<Button-1>", lambda e_: escolher())
        ttk.Button(f, text="Escolher…", command=escolher).pack(side="left", padx=(6, 0))
        return f

    # ---------------------------------------------------------------- Geral
    g = ttk.Frame(abas, padding=12); abas.add(g, text="Geral")
    v_tit = tk.StringVar(value=cfg["titulo"]); v_sub = tk.StringVar(value=cfg["subtitulo"])
    v_resp = tk.StringVar(value=cfg["responsavel"]); v_logo = tk.StringVar(value=cfg["logo"])
    v_dec = tk.StringVar(value="vírgula (1,5)" if cfg["decimal"] == "," else "ponto (1.5)")
    v_perg = tk.BooleanVar(value=cfg["perguntar"])
    linhas = [("Título do relatório", ttk.Entry(g, textvariable=v_tit, width=58)),
              ("Subtítulo (empresa, cliente, sistema)", ttk.Entry(g, textvariable=v_sub, width=58)),
              ("Responsável técnico", ttk.Entry(g, textvariable=v_resp, width=58))]
    for i, (rot, w) in enumerate(linhas):
        ttk.Label(g, text=rot).grid(row=i, column=0, sticky="w", pady=4, padx=(0, 12)); w.grid(row=i, column=1, columnspan=2, sticky="we")
    ttk.Label(g, text="Logo (PNG, JPG ou SVG)").grid(row=3, column=0, sticky="w", pady=4)
    fl = ttk.Frame(g); fl.grid(row=3, column=1, columnspan=2, sticky="we")
    ttk.Entry(fl, textvariable=v_logo, width=44).pack(side="left", fill="x", expand=True)
    ttk.Button(fl, text="Procurar…", command=lambda: v_logo.set(filedialog.askopenfilename(
        parent=r, title="Escolher logo", filetypes=[("Imagens", "*.png *.jpg *.jpeg *.svg"), ("Todos", "*.*")]) or v_logo.get())).pack(side="left", padx=4)
    ttk.Button(fl, text="Limpar", command=lambda: v_logo.set("")).pack(side="left")
    ttk.Label(g, text="Separador decimal").grid(row=4, column=0, sticky="w", pady=4)
    ttk.Combobox(g, textvariable=v_dec, values=["ponto (1.5)", "vírgula (1,5)"], state="readonly", width=16).grid(row=4, column=1, sticky="w")
    ttk.Checkbutton(g, text="Abrir esta janela antes de cada relatório", variable=v_perg).grid(row=5, column=0, columnspan=3, sticky="w", pady=(12, 0))
    g.columnconfigure(1, weight=1)

    # ---------------------------------------------------------------- Critérios
    c = ttk.Frame(abas, padding=12); abas.add(c, text="Critérios")
    v_crit = {}
    for i, (k, rot, un) in enumerate(NOMES_CRITERIOS):
        v_crit[k] = tk.StringVar(value=("%g" % cfg["criterios"][k]))
        ttk.Label(c, text=rot).grid(row=i, column=0, sticky="w", pady=4, padx=(0, 12))
        ttk.Entry(c, textvariable=v_crit[k], width=10).grid(row=i, column=1, sticky="w")
        ttk.Label(c, text=un, style="Nota.TLabel").grid(row=i, column=2, sticky="w", padx=6)
    ttk.Label(c, text="Se o cadastro da ferramenta no EPANET tiver números depois de $INPFILE,\n"
                      "eles têm prioridade sobre estes valores (P mín, P máx, V mín, V máx, K1).",
              style="Nota.TLabel", justify="left").grid(row=len(NOMES_CRITERIOS), column=0, columnspan=3, sticky="w", pady=(12, 0))

    # ---------------------------------------------------------------- Cores
    co = ttk.Frame(abas, padding=12); abas.add(co, text="Cores")
    v_cor = {}
    for i, (k, rot) in enumerate(NOMES_CORES):
        v_cor[k] = tk.StringVar(value=cfg["cores"][k])
        ttk.Label(co, text=rot).grid(row=i, column=0, sticky="w", pady=4, padx=(0, 12))
        amostra(co, v_cor[k]).grid(row=i, column=1, sticky="w")
    ttk.Label(co, text="Clique no quadrado ou em Escolher… para abrir a paleta. Também aceita o código hex (#RRGGBB).",
              style="Nota.TLabel").grid(row=len(NOMES_CORES), column=0, columnspan=2, sticky="w", pady=(12, 0))

    # ---------------------------------------------------------------- Mapas
    m = ttk.Frame(abas, padding=8); abas.add(m, text="Mapas")
    sub = ttk.Notebook(m); sub.pack(fill="both", expand=True)
    v_mapa = {}

    for chave, nome, un in MAPAS_CLASSES:
        f = ttk.Frame(sub, padding=10); sub.add(f, text=nome)
        d = cfg["mapas"][chave]
        v = {"ativo": tk.BooleanVar(value=d["ativo"]), "limites": tk.StringVar(value="; ".join("%g" % x for x in d["limites"])),
             "cores": [tk.StringVar(value=x) for x in d["cores"]]}
        v_mapa[chave] = v
        ttk.Checkbutton(f, text="Incluir este mapa no relatório", variable=v["ativo"]).grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Label(f, text="Limites das classes (%s), separados por ;" % un).grid(row=1, column=0, sticky="w", pady=(10, 2))
        ttk.Entry(f, textvariable=v["limites"], width=30).grid(row=2, column=0, sticky="w")
        quadro = ttk.Frame(f); quadro.grid(row=3, column=0, columnspan=3, sticky="w", pady=(10, 0))

        def montar(v=v, quadro=quadro, un=un):
            for w in quadro.winfo_children():
                w.destroy()
            try:
                lims = [float(x.replace(",", ".")) for x in re.split(r"[;\s]+", v["limites"].get().strip()) if x]
            except ValueError:
                messagebox.showerror("Limites inválidos", "Use números separados por ponto e vírgula, ex.: 10; 20; 30", parent=r); return
            precisa = len(lims) + 1
            while len(v["cores"]) < precisa:
                v["cores"].append(tk.StringVar(value=v["cores"][-1].get() if v["cores"] else "#034EA2"))
            del v["cores"][precisa:]
            rot = ["< %g" % lims[0]] + ["%g – %g" % (lims[i], lims[i + 1]) for i in range(len(lims) - 1)] + ["> %g %s" % (lims[-1], un)] if lims else ["todas"]
            for i, txt in enumerate(rot):
                ttk.Label(quadro, text=txt, width=14).grid(row=i, column=0, sticky="w", pady=2)
                amostra(quadro, v["cores"][i]).grid(row=i, column=1, sticky="w")
        ttk.Button(f, text="Atualizar classes", command=montar).grid(row=2, column=1, sticky="w", padx=8)
        montar()

    for chave, nome, nota in MAPAS_RAMPA:
        f = ttk.Frame(sub, padding=10); sub.add(f, text=nome)
        d = cfg["mapas"][chave]
        v = {"ativo": tk.BooleanVar(value=d["ativo"]), "rampa": [tk.StringVar(value=x) for x in d["rampa"]]}
        v_mapa[chave] = v
        ttk.Checkbutton(f, text="Incluir este mapa no relatório", variable=v["ativo"]).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(f, text="Rampa de cores (%s)" % nota, style="Nota.TLabel").grid(row=1, column=0, columnspan=2, sticky="w", pady=(10, 4))
        for i, rot in enumerate(("Cor dos valores baixos", "Cor dos valores altos")):
            ttk.Label(f, text=rot).grid(row=2 + i, column=0, sticky="w", pady=3, padx=(0, 12))
            amostra(f, v["rampa"][i]).grid(row=2 + i, column=1, sticky="w")

    # ---------------------------------------------------------------- Seções
    s = ttk.Frame(abas, padding=12); abas.add(s, text="Seções")
    v_sec = {}
    ttk.Label(s, text="Seções incluídas no relatório:").grid(row=0, column=0, sticky="w", pady=(0, 6))
    for i, (k, rot) in enumerate(NOMES_SECOES):
        v_sec[k] = tk.BooleanVar(value=cfg["secoes"][k])
        ttk.Checkbutton(s, text=rot, variable=v_sec[k]).grid(row=1 + i % 5, column=i // 5, sticky="w", pady=2, padx=(0, 24))

    # ---------------------------------------------------------------- coleta e botões
    def coletar():
        novo = copy.deepcopy(cfg)
        novo.update(titulo=v_tit.get().strip() or PADRAO["titulo"], subtitulo=v_sub.get().strip(),
                    responsavel=v_resp.get().strip(), logo=v_logo.get().strip(),
                    decimal="," if v_dec.get().startswith("v") else ".", perguntar=bool(v_perg.get()))
        for k, rot, _ in NOMES_CRITERIOS:
            try:
                novo["criterios"][k] = float(v_crit[k].get().replace(",", "."))
            except ValueError:
                raise ValueError("Critério inválido: %s" % rot)
        for k, rot in NOMES_CORES:
            val = v_cor[k].get().strip()
            if not HEX.match(val):
                raise ValueError("Cor inválida em %s: %s (use #RRGGBB)" % (rot, val))
            novo["cores"][k] = val.upper()
        for chave, nome, _ in MAPAS_CLASSES:
            v = v_mapa[chave]
            try:
                lims = [float(x.replace(",", ".")) for x in re.split(r"[;\s]+", v["limites"].get().strip()) if x]
            except ValueError:
                raise ValueError("Limites inválidos no mapa de %s" % nome)
            if not lims or any(b <= a for a, b in zip(lims, lims[1:])):
                raise ValueError("No mapa de %s os limites precisam ser crescentes." % nome)
            cores = [x.get().strip().upper() for x in v["cores"]]
            if len(cores) != len(lims) + 1:
                raise ValueError("No mapa de %s clique em Atualizar classes depois de mudar os limites." % nome)
            if not all(HEX.match(x) for x in cores):
                raise ValueError("Há uma cor inválida no mapa de %s." % nome)
            novo["mapas"][chave] = {"ativo": bool(v["ativo"].get()), "limites": lims, "cores": cores}
        for chave, nome, _ in MAPAS_RAMPA:
            v = v_mapa[chave]
            rampa = [x.get().strip().upper() for x in v["rampa"]]
            if not all(HEX.match(x) for x in rampa):
                raise ValueError("Há uma cor inválida no mapa de %s." % nome)
            novo["mapas"][chave] = {"ativo": bool(v["ativo"].get()), "rampa": rampa}
        for k, _ in NOMES_SECOES:
            novo["secoes"][k] = bool(v_sec[k].get())
        return novo

    def com_validacao(acao):
        def f():
            try:
                acao(coletar())
            except ValueError as e:
                messagebox.showerror("Verifique a configuração", str(e), parent=r)
        return f

    def acao_salvar(novo):
        salvar(novo); resultado["cfg"] = novo
        if not botao_gerar:
            messagebox.showinfo("Configuração salva", "Os próximos relatórios usarão estas escolhas.", parent=r)

    def acao_gerar(novo):
        salvar(novo); resultado["cfg"] = novo; r.destroy()

    def acao_previa(novo):
        tmp = os.path.join(tempfile.gettempdir(), "IARHA_config_previa.json")
        salvar(novo, tmp)
        demo = os.path.join(AQUI, "rede_demo.inp")
        env = dict(os.environ, IARHA_CONFIG=tmp, IARHA_SEM_JANELA="1")
        exe = sys.executable.replace("pythonw.exe", "python.exe") if os.name == "nt" else sys.executable
        subprocess.Popen([exe, os.path.join(AQUI, "06_relatorio_analise_rede.py"), demo], env=env, cwd=AQUI,
                         creationflags=0x08000000 if os.name == "nt" else 0)

    def restaurar():
        if messagebox.askyesno("Restaurar padrão", "Voltar todas as opções ao padrão IARHA?", parent=r):
            r.destroy(); resultado["restaurar"] = True

    b = ttk.Frame(raiz); b.pack(fill="x", pady=(10, 0))
    ttk.Button(b, text="Restaurar padrão", command=restaurar).pack(side="left")
    ttk.Button(b, text="Gerar prévia (rede de demonstração)", command=com_validacao(acao_previa)).pack(side="left", padx=6)
    ttk.Button(b, text="Cancelar" if botao_gerar else "Fechar", command=r.destroy).pack(side="right")
    if botao_gerar:
        ttk.Button(b, text="Gerar relatório", command=com_validacao(acao_gerar)).pack(side="right", padx=6)
    else:
        ttk.Button(b, text="Salvar", command=com_validacao(acao_salvar)).pack(side="right", padx=6)
    r.mainloop()
    if resultado.get("restaurar"):
        salvar(copy.deepcopy(PADRAO))
        return janela(copy.deepcopy(PADRAO), botao_gerar)
    return resultado["cfg"]
