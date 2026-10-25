# -*- coding: utf-8 -*-
"""
Ferramenta 3 — Rugosidade em Lote  (ALTERA o projeto)
Uso (parâmetros no EPANET):  "<pasta>\\03_rugosidade_lote.py" "$INPFILE"
Marque "Atualizar EPANET ao fechar" na configuração da ferramenta para que
o projeto seja recarregado com as rugosidades novas.

Abre uma janela para escolher: faixa de diâmetro, operação (definir valor
ou multiplicar) e valor. Grava o INP e um backup .bak ao lado.
Uso sem janela (testes):  03_rugosidade_lote.py arquivo.inp definir|multiplicar VALOR [DMIN DMAX]
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from epanet_comum import Inp, substituir_campo, arg_arquivo, avisar


def aplicar(inp, operacao, valor, dmin, dmax):
    n = 0
    for i, tok in inp.secoes.get("PIPES", []):
        D, C = float(tok[4]), float(tok[5])
        if dmin <= D <= dmax:
            novo = valor if operacao == "definir" else C * valor
            inp.linhas[i] = substituir_campo(inp.linhas[i], 5, ("%.6g" % novo))
            n += 1
    return n


def janela(inp):
    import tkinter as tk
    from tkinter import ttk, messagebox
    diams = sorted({float(t[4]) for t in inp.tabela("PIPES")})
    res = {}
    r = tk.Tk()
    r.title("Rugosidade em Lote — EPANET 2.2 Brasil")
    r.resizable(False, False)
    f = ttk.Frame(r, padding=14); f.grid()
    ttk.Label(f, text="Fórmula de perda de carga: %s   ·   %d tubulações"
              % (inp.formula(), len(inp.tabela("PIPES")))).grid(columnspan=2, sticky="w", pady=(0, 10))
    v_dmin = tk.StringVar(value=("%g" % diams[0]) if diams else "0")
    v_dmax = tk.StringVar(value=("%g" % diams[-1]) if diams else "99999")
    v_op = tk.StringVar(value="definir")
    v_val = tk.StringVar(value="130" if inp.formula() == "H-W" else "0.1")
    for lin, (rot, var) in enumerate([("Diâmetro mínimo", v_dmin), ("Diâmetro máximo", v_dmax)], start=1):
        ttk.Label(f, text=rot).grid(row=lin, column=0, sticky="w")
        ttk.Entry(f, textvariable=var, width=12).grid(row=lin, column=1, sticky="w", pady=2)
    ttk.Label(f, text="Operação").grid(row=3, column=0, sticky="w")
    ttk.Combobox(f, textvariable=v_op, values=["definir", "multiplicar"], state="readonly",
                 width=10).grid(row=3, column=1, sticky="w", pady=2)
    ttk.Label(f, text="Valor").grid(row=4, column=0, sticky="w")
    ttk.Entry(f, textvariable=v_val, width=12).grid(row=4, column=1, sticky="w", pady=2)

    def ok():
        try:
            res.update(op=v_op.get(), val=float(v_val.get().replace(",", ".")),
                       dmin=float(v_dmin.get().replace(",", ".")), dmax=float(v_dmax.get().replace(",", ".")))
        except ValueError:
            messagebox.showerror("Valor inválido", "Use números (vírgula ou ponto)."); return
        r.destroy()

    b = ttk.Frame(f); b.grid(row=5, columnspan=2, pady=(12, 0), sticky="e")
    ttk.Button(b, text="Cancelar", command=r.destroy).pack(side="right", padx=4)
    ttk.Button(b, text="Aplicar", command=ok).pack(side="right")
    r.mainloop()
    return res


def main():
    inp = Inp(arg_arquivo(1, "$INPFILE"))
    if len(sys.argv) >= 4:
        op, val = sys.argv[2], float(sys.argv[3])
        dmin = float(sys.argv[4]) if len(sys.argv) > 4 else 0.0
        dmax = float(sys.argv[5]) if len(sys.argv) > 5 else 1e9
        silencioso = True
    else:
        p = janela(inp)
        if not p:
            return  # cancelado: nada é gravado
        op, val, dmin, dmax = p["op"], p["val"], p["dmin"], p["dmax"]
        silencioso = False
    n = aplicar(inp, op, val, dmin, dmax)
    if n:
        inp.salvar()
    msg = "%d tubulações alteradas (%s %g, diâmetros %g a %g).\nBackup: %s.bak" % (
        n, op, val, dmin, dmax, os.path.basename(inp.caminho))
    print(msg) if silencioso else avisar("Rugosidade em Lote", msg)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        avisar("Rugosidade em Lote — erro", str(e), erro=True)
