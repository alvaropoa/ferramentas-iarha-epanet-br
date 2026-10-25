# -*- coding: utf-8 -*-
"""
Ferramenta 2 — Verificador de Consistência
Uso (parâmetros no EPANET):  "<pasta>\\02_verificar_consistencia.py" "$INPFILE"
Aponta problemas comuns de cadastro antes de simular. Não altera o projeto.
"""
import os, sys
from collections import defaultdict, deque
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from epanet_comum import Inp, arg_arquivo, gravar_relatorio, tabela_html, esc, avisar

# faixas plausíveis de rugosidade por fórmula
FAIXA_RUG = {"H-W": (40.0, 150.0), "D-W": (0.0, 10.0), "C-M": (0.008, 0.035)}


def verificar(inp):
    """Lista de (gravidade, categoria, objeto, detalhe), erros primeiro. Usada também pela ferramenta 5."""
    form = inp.formula()
    achados = []  # (gravidade, categoria, objeto, detalhe)
    add = lambda g, c, o, d: achados.append((g, c, o, d))

    juncoes = {t[0]: t for t in inp.tabela("JUNCTIONS")}
    fontes = [t[0] for t in inp.tabela("RESERVOIRS")] + [t[0] for t in inp.tabela("TANKS")]
    nos = set(juncoes) | set(fontes)
    coords = {t[0] for t in inp.tabela("COORDINATES")}

    # IDs duplicados entre nós
    vistos = defaultdict(int)
    for sec in ("JUNCTIONS", "RESERVOIRS", "TANKS"):
        for t in inp.tabela(sec):
            vistos[t[0]] += 1
    for i, n in vistos.items():
        if n > 1:
            add("erro", "ID duplicado", i, "nó definido %d vezes" % n)

    if not fontes:
        add("erro", "Sem fonte", "—", "rede sem reservatório de nível fixo nem variável")

    # trechos
    adj = defaultdict(set)       # só trechos abertos (para alcance)
    ligados = set()              # qualquer trecho (para nó isolado)
    fechados = {t[0] for t in inp.tabela("PIPES") if len(t) > 7 and t[7].upper() == "CLOSED"}
    for sec in ("PIPES", "PUMPS", "VALVES"):
        for t in inp.tabela(sec):
            lid, n1, n2 = t[0], t[1], t[2]
            for n in (n1, n2):
                if n not in nos:
                    add("erro", "Nó inexistente", lid, "liga ao nó '%s', que não existe" % n)
            if n1 == n2:
                add("erro", "Laço", lid, "nó inicial e final iguais (%s)" % n1)
            ligados.update((n1, n2))
            if lid not in fechados:
                adj[n1].add(n2); adj[n2].add(n1)

    lo, hi = FAIXA_RUG.get(form, (None, None))
    for t in inp.tabela("PIPES"):
        lid, L, D, C = t[0], float(t[3]), float(t[4]), float(t[5])
        if L <= 0:
            add("erro", "Comprimento", lid, "comprimento %g" % L)
        elif L < 1:
            add("aviso", "Comprimento", lid, "trecho muito curto (%g)" % L)
        if D <= 0:
            add("erro", "Diâmetro", lid, "diâmetro %g" % D)
        if lo is not None and not (lo <= C <= hi):
            add("aviso", "Rugosidade", lid, "%g fora da faixa usual %s (%g–%g)" % (C, form, lo, hi))

    # nós
    for j, t in juncoes.items():
        if j not in ligados:
            add("erro", "Nó isolado", j, "nenhum trecho conectado")
        if len(t) > 1 and float(t[1]) == 0.0:
            add("aviso", "Cota zero", j, "cota = 0 — possivelmente não preenchida")
    for n in nos:
        if n not in coords:
            add("aviso", "Sem coordenada", n, "nó não aparece no mapa")

    # conectividade a partir das fontes (ignora tubos fechados)
    alcance = set(fontes)
    fila = deque(fontes)
    while fila:
        n = fila.popleft()
        for v in adj[n]:
            if v not in alcance:
                alcance.add(v); fila.append(v)
    sem_fonte = [j for j in juncoes if j in ligados and j not in alcance]
    if fontes:
        for j in sem_fonte:
            add("erro", "Sem abastecimento", j, "não há caminho até nenhum reservatório")

    ordem = {"erro": 0, "aviso": 1}
    achados.sort(key=lambda a: (ordem[a[0]], a[1], a[2]))
    return achados


def main():
    inp = Inp(arg_arquivo(1, "$INPFILE"))
    achados = verificar(inp)
    ordem = {"erro": 0, "aviso": 1}
    nos = {t[0] for s in ("JUNCTIONS", "RESERVOIRS", "TANKS") for t in inp.tabela(s)}

    # ---- relatório
    ne = sum(1 for a in achados if a[0] == "erro")
    na = len(achados) - ne
    corpo = "<div class='kpis'>"
    corpo += "<div class='kpi'><b class='err'>%d</b><span>erros</span></div>" % ne
    corpo += "<div class='kpi'><b class='warn'>%d</b><span>avisos</span></div>" % na
    corpo += "<div class='kpi'><b>%d</b><span>nós verificados</span></div>" % len(nos)
    corpo += "<div class='kpi'><b>%d</b><span>trechos verificados</span></div>" % (
        len(inp.tabela("PIPES")) + len(inp.tabela("PUMPS")) + len(inp.tabela("VALVES")))
    corpo += "</div>"
    if achados:
        # resumo por categoria
        cat = defaultdict(int)
        for a in achados:
            cat[(a[0], a[1])] += 1
        corpo += "<h2>Por categoria</h2>" + tabela_html(
            ["Gravidade", "Categoria", "Ocorrências"],
            [["<span class='tag %s'>%s</span>" % ("err" if g == "erro" else "warn", g), esc(c), n]
             for (g, c), n in sorted(cat.items(), key=lambda x: (ordem[x[0][0]], -x[1]))], (2,))
        corpo += "<h2>Detalhe</h2>" + tabela_html(
            ["Gravidade", "Categoria", "Objeto", "Detalhe"],
            [["<span class='tag %s'>%s</span>" % ("err" if g == "erro" else "warn", g),
              esc(c), "<b>%s</b>" % esc(o), esc(d)] for g, c, o, d in achados[:2000]])
    else:
        corpo += "<h2 class='ok'>Nenhum problema encontrado.</h2>"

    gravar_relatorio("Verificação de Consistência", os.path.basename(inp.caminho),
                     corpo, "epanet_verificacao.html")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        avisar("Verificador — erro", str(e), erro=True)
