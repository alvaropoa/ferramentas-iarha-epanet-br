# -*- coding: utf-8 -*-
"""
Ferramenta 4 — Pressões e Velocidades (NBR 12218)
Uso (parâmetros no EPANET):  "<pasta>\\04_pressoes_nbr12218.py" $INPFILE
Opcional: limites  PMIN PMAX VMIN VMAX  (padrão 10 40 0.4 3.5, em mca e m/s)
Ex.:  "<pasta>\\04_pressoes_nbr12218.py" $INPFILE 10 50 0.4 3.5

Simula o projeto com o runepanet.exe do próprio EPANET 2.2 Brasil (o menu não
oferece $OUTFILE) e lista, para todo o período simulado, nós com pressão mínima
abaixo / máxima acima do limite e trechos com velocidade fora da faixa.
Observação: a máxima simulada é usada como aproximação da pressão estática.
Não altera o projeto.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from epanet_comum import (SaidaBinaria, arg_arquivo, gravar_relatorio, tabela_html, fmt, esc,
                          avisar, UNID_PRESSAO, resultados_de, numeros)

CONV_P = {0: 0.7030696, 1: 0.1019716, 2: 1.0, 3: 10.19716, 4: 0.3048}   # unidade do arquivo -> mca


def main():
    out = SaidaBinaria(resultados_de(arg_arquivo(1, "$INPFILE")))
    pmin, pmax, vmin, vmax = numeros(sys.argv[2:], [10.0, 40.0, 0.4, 3.5])
    k = CONV_P.get(out.u_pressao, 1.0)
    si = out.u_vazao >= 5
    uv = "m/s" if si else "ft/s"
    if not si:
        vmin, vmax = vmin / 0.3048, vmax / 0.3048

    juncs = [i for i in range(out.nn) if i not in out.idx_fontes]
    tubos = [j for j in range(out.nl) if out.link_tipo[j] <= 1]
    p_min = {i: (1e9, 0) for i in juncs}; p_max = {i: (-1e9, 0) for i in juncs}
    v_max = {j: (0.0, 0) for j in tubos}

    for kp in range(out.nperiodos):
        pres, vel, _, sta = out.periodo(kp)
        for i in juncs:
            p = pres[i] * k
            if p < p_min[i][0]: p_min[i] = (p, kp)
            if p > p_max[i][0]: p_max[i] = (p, kp)
        for j in tubos:
            if sta[j] <= 2:  # fechado: não conta
                continue
            v = abs(vel[j])
            if v > v_max[j][0]: v_max[j] = (v, kp)

    baixa = sorted([(p_min[i][0], i) for i in juncs if p_min[i][0] < pmin])
    alta = sorted([(p_max[i][0], i) for i in juncs if p_max[i][0] > pmax], reverse=True)
    rapida = sorted([(v_max[j][0], j) for j in tubos if v_max[j][0] > vmax], reverse=True)
    lenta = sorted([(v_max[j][0], j) for j in tubos if v_max[j][0] < vmin])

    ok = lambda n, tot: "ok" if n == 0 else ("warn" if n <= 0.05 * max(tot, 1) else "err")
    corpo = "<div class='kpis'>"
    for n, tot, rot in [(len(baixa), len(juncs), "nós com P mín < %s mca" % fmt(pmin, 0)),
                        (len(alta), len(juncs), "nós com P máx > %s mca" % fmt(pmax, 0)),
                        (len(rapida), len(tubos), "tubos com V > %s %s" % (fmt(vmax, 1), uv)),
                        (len(lenta), len(tubos), "tubos com V máx < %s %s" % (fmt(vmin, 1), uv))]:
        corpo += "<div class='kpi'><b class='%s'>%d</b><span>%s</span></div>" % (ok(n, tot), n, esc(rot))
    corpo += "</div>"

    pm_rede = min(p_min[i][0] for i in juncs) if juncs else 0
    pM_rede = max(p_max[i][0] for i in juncs) if juncs else 0
    corpo += ("<p class='sub' style='margin-top:14px'>%d nós de consumo · %d tubulações · %d períodos "
              "· pressão na rede de %s a %s mca</p>") % (len(juncs), len(tubos), out.nperiodos,
                                                        fmt(pm_rede, 1), fmt(pM_rede, 1))

    def bloco(titulo, lista, nomes, unid, cls):
        if not lista:
            return "<h2>%s</h2><p class='ok'>Nenhum.</p>" % esc(titulo)
        return "<h2>%s</h2>" % esc(titulo) + tabela_html(
            ["Objeto", "Valor (%s)" % unid, "Hora"],
            [["<b>%s</b>" % esc(nomes[i]), "<span class='%s'>%s</span>" % (cls, fmt(v, 2)),
              out.hora(per)] for v, i, per in lista[:500]], (1,))

    corpo += bloco("Pressão mínima abaixo de %s mca" % fmt(pmin, 0),
                   [(v, i, p_min[i][1]) for v, i in baixa], out.nos, "mca", "err")
    corpo += bloco("Pressão máxima acima de %s mca" % fmt(pmax, 0),
                   [(v, i, p_max[i][1]) for v, i in alta], out.nos, "mca", "warn")
    corpo += bloco("Velocidade acima de %s %s" % (fmt(vmax, 1), uv),
                   [(v, j, v_max[j][1]) for v, j in rapida], out.links, uv, "err")
    corpo += bloco("Velocidade máxima abaixo de %s %s" % (fmt(vmin, 1), uv),
                   [(v, j, v_max[j][1]) for v, j in lenta], out.links, uv, "warn")

    gravar_relatorio("Pressões e Velocidades — NBR 12218",
                     "Limites: P %s–%s mca · V %s–%s %s · pressão do arquivo em %s"
                     % (fmt(pmin, 0), fmt(pmax, 0), fmt(vmin, 1), fmt(vmax, 1), uv,
                        UNID_PRESSAO.get(out.u_pressao, "?")),
                     corpo, "epanet_nbr12218.html")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        avisar("Pressões NBR 12218 — erro", str(e), erro=True)
