"""Cálculo de dose e redação de posologia a partir da dose decidida pelo Erik.

A dose (mg/kg) vem sempre do Erik: no pedido do atendimento ou como dose
padrão que ele mesmo cadastrou no catálogo. Este módulo só faz a conta,
arredonda para o que é possível administrar e escreve a posologia.
"""
from fractions import Fraction

FRAC_TXT = {Fraction(1, 4): "¼", Fraction(1, 2): "½", Fraction(3, 4): "¾"}
FREQ_TXT = {24: "a cada 24 horas", 12: "a cada 12 horas", 8: "a cada 8 horas", 6: "a cada 6 horas", 48: "a cada 48 horas"}


def br(n, casas=2):
    s = f"{n:.{casas}f}".rstrip("0").rstrip(".")
    return s.replace(".", ",")


def qtd_comprimido(fr):
    inteiro = fr.numerator // fr.denominator
    resto = fr - inteiro
    partes = []
    if inteiro:
        partes.append(str(inteiro))
    if resto:
        partes.append(FRAC_TXT.get(resto, f"{resto.numerator}/{resto.denominator}"))
    txt = " e ".join(partes) if len(partes) > 1 else partes[0]
    return txt


def calcular(peso_kg, dose_mg_kg, produto, freq_h, dias=None, continuo=False, se_necessario=False):
    """produto: dict do catálogo com 'forma' ('comprimido'|'capsula'|'liquido'),
    'mg_por_unidade' (comprimido/cápsula) ou 'mg_por_ml' (líquido),
    'fracao_minima' (comprimido: 1, 0.5 ou 0.25) e 'unidades_por_embalagem' ou 'ml_por_embalagem'."""
    alvo = peso_kg * dose_mg_kg
    forma = produto["forma"]
    linhas = [f"{br(peso_kg)} kg × {br(dose_mg_kg, 3)} mg/kg = {br(alvo, 3)} mg"]
    alertas = []
    if forma in ("comprimido", "capsula"):
        conc = produto["mg_por_unidade"]
        bruto = alvo / conc
        passo = Fraction(str(produto.get("fracao_minima", 1))).limit_denominator(4)
        n = Fraction(round(bruto / float(passo))) * passo
        if n == 0:
            n = passo
            alertas.append("A menor fração possível ainda fica acima da dose. Conferir outra apresentação.")
        real = float(n) * conc
        unidade = "comprimido" if forma == "comprimido" else "cápsula"
        plural = unidade + ("s" if n > 1 else "")
        tomada = f"{qtd_comprimido(n)} {plural if n > 1 else unidade}"
        linhas.append(f"{br(alvo, 3)} mg ÷ {br(conc)} mg/{unidade} = {br(bruto, 3)} {unidade} → arredondado para {qtd_comprimido(n)} ({br(real, 3)} mg)")
        por_tomada = float(n)
        un_emb = produto.get("unidades_por_embalagem")
    else:
        conc = produto["mg_por_ml"]
        bruto = alvo / conc
        precisao = produto.get("precisao_ml", 0.1)
        ml = max(round(bruto / precisao) * precisao, precisao)
        real = ml * conc
        tomada = f"{br(ml)} mL"
        linhas.append(f"{br(alvo, 3)} mg ÷ {br(conc)} mg/mL = {br(bruto, 3)} mL → arredondado para {br(ml)} mL ({br(real, 3)} mg)")
        por_tomada = ml
        un_emb = produto.get("ml_por_embalagem")
    real_kg = real / peso_kg
    desvio = (real - alvo) / alvo * 100
    linhas.append(f"dose real: {br(real_kg, 3)} mg/kg ({'+' if desvio >= 0 else ''}{br(desvio, 1)}% da dose decidida)")
    if abs(desvio) > 10:
        alertas.append(f"Arredondamento desvia {br(abs(desvio), 1)}% da dose decidida.")

    freq = FREQ_TXT.get(freq_h, f"a cada {freq_h} horas")
    if se_necessario:
        pos = f"Dar **{tomada}** {freq}, **somente se necessário**."
    elif continuo:
        pos = f"Dar **{tomada}** **{freq}**. Uso contínuo."
    else:
        pos = f"Dar **{tomada}** **{freq}** por **{dias} dias**."

    total_txt = None
    if dias and not se_necessario:
        tomadas = int(24 / freq_h * dias) if freq_h <= 24 else int(dias * 24 / freq_h)
        total = por_tomada * tomadas
        u = "mL" if forma == "liquido" else ("comprimidos" if forma == "comprimido" else "cápsulas")
        total_txt = f"{tomadas} tomadas × {br(por_tomada, 3)} = {br(total, 3)} {u}"
        if un_emb:
            import math
            emb = math.ceil(total / un_emb)
            total_txt += f" → {emb} embalage{'m' if emb == 1 else 'ns'} de {br(un_emb)}"
        linhas.append("total: " + total_txt)
    return {"posologia": pos, "memoria": linhas, "alertas": alertas}


if __name__ == "__main__":
    cerenia = {"forma": "comprimido", "mg_por_unidade": 16, "fracao_minima": 0.25, "unidades_por_embalagem": 4}
    r = calcular(4.2, 1, cerenia, 24, dias=5)
    print(r["posologia"]); print("\n".join(r["memoria"])); print(r["alertas"])
