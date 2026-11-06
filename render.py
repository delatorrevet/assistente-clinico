#!/usr/bin/env python3
"""Gera os PDFs do Assistente Clínico na identidade Dr. Erik Dellatorre.

Uso: python3 render.py atendimento.json [pasta_saida]

O JSON traz "codigo", "data", "paciente", "responsavel" e um ou mais blocos:
"receita", "exames", "orientacoes". Gera um PDF por bloco e um arquivo
<codigo>_conferencia.txt com a memória de cálculo das doses.

Itens da receita podem citar um produto do catálogo ("produto": "cerenia-16")
e pedir cálculo ("calculo": {"dose_mg_kg": 1, "freq_h": 24, "dias": 5}).
A dose é sempre a decidida pelo Erik.

Marcações de texto: **negrito** e [[pendente]] (marca amarela para confirmar).
"""
import json, re, sys, datetime, html
from pathlib import Path
from jinja2 import Environment, BaseLoader
from weasyprint import HTML
from calc import calcular

AQUI = Path(__file__).resolve().parent
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]
ORDEM_FARM = ["veterinária", "humana", "manipulação"]

ICONE = {
    "veterinária": '<svg viewBox="0 0 24 24"><g fill="#8a8292"><ellipse cx="6" cy="9" rx="2.2" ry="2.8"/><ellipse cx="10" cy="5.5" rx="2.2" ry="2.8"/><ellipse cx="14.5" cy="5.5" rx="2.2" ry="2.8"/><ellipse cx="18.5" cy="9" rx="2.2" ry="2.8"/><path d="M12 11c-3.5 0-6.5 4-6.5 6.5 0 2 1.6 3 3.2 3 1.4 0 2.2-.8 3.3-.8s1.9.8 3.3.8c1.6 0 3.2-1 3.2-3C18.5 15 15.5 11 12 11z"/></g></svg>',
    "humana": '<svg viewBox="0 0 24 24"><g fill="#8a8292"><circle cx="12" cy="7.5" r="4"/><path d="M4 21c0-4.4 3.6-7.5 8-7.5s8 3.1 8 7.5z"/></g></svg>',
    "manipulação": '<svg viewBox="0 0 24 24"><g fill="#8a8292"><path d="M9 3h6v2h-1v4.2l5 8.3A2.3 2.3 0 0 1 17 21H7a2.3 2.3 0 0 1-2-3.5l5-8.3V5H9z"/></g></svg>',
}


EXAME_ICONE = {
    "sangue": '<svg viewBox="0 0 24 24"><g fill="none" stroke="#6728BF" stroke-width="1.8" stroke-linecap="round"><path d="M9 2.5h6M10 2.5v15a2 2 0 0 0 4 0v-15"/></g><path fill="#e85349" d="M10.9 11h2.2v6.5a1.1 1.1 0 0 1-2.2 0z"/></svg>',
    "urina": '<svg viewBox="0 0 24 24"><path fill="#F9AD59" stroke="#6728BF" stroke-width="1.6" d="M12 3s6 6.8 6 11a6 6 0 0 1-12 0c0-4.2 6-11 6-11z"/></svg>',
    "fezes": '<svg viewBox="0 0 24 24"><g fill="none" stroke="#6728BF" stroke-width="1.8" stroke-linejoin="round"><rect x="6" y="3" width="12" height="4" rx="1"/><path d="M7 7h10l-1 13H8z"/></g></svg>',
    "imagem": '<svg viewBox="0 0 24 24"><g fill="none" stroke="#6728BF" stroke-width="1.8" stroke-linecap="round"><rect x="3" y="4" width="18" height="13" rx="2"/><path d="M8 21h8M7 13c2-4 8-4 10 0"/></g><circle cx="12" cy="13" r="1.4" fill="#F9AD59"/></svg>',
    "citologia": '<svg viewBox="0 0 24 24"><g fill="none" stroke="#6728BF" stroke-width="1.8" stroke-linecap="round"><path d="M9 3l4 7M7 4.5l3-1.5M6 20h12M9 20a6 6 0 0 0 9-6"/><circle cx="12.5" cy="12" r="2"/></g></svg>',
    "rapido": '<svg viewBox="0 0 24 24"><g fill="none" stroke="#6728BF" stroke-width="1.8"><rect x="7" y="2.5" width="10" height="19" rx="2.5"/></g><rect x="10" y="6" width="4" height="5" rx="1" fill="#F9AD59"/><circle cx="12" cy="16" r="1.6" fill="#6728BF"/></svg>',
    "outro": '<svg viewBox="0 0 24 24"><g fill="none" stroke="#6728BF" stroke-width="1.8" stroke-linejoin="round"><path d="M9 3h6M10 3v6l-5 9a2 2 0 0 0 1.8 3h10.4a2 2 0 0 0 1.8-3l-5-9V3"/></g><path fill="#F9AD59" d="M7.5 15h9l1.6 3H5.9z"/></svg>',
}


def tipo_exame(x):
    if x.get("tipo"):
        return x["tipo"]
    t = (x.get("nome", "") + " " + (x.get("material") or "")).lower()
    if any(k in t for k in ("snap", "teste rápido", "elisa")):
        return "rapido"
    if "urin" in t:
        return "urina"
    if any(k in t for k in ("fezes", "coproparasit", "fecal")):
        return "fezes"
    if any(k in t for k in ("citolog", "biópsia", "histopat", "paaf")):
        return "citologia"
    if any(k in t for k in ("ultrass", "radiogr", "raio", "ecocardio", "eletrocardio", "tomogra", "imagem")):
        return "imagem"
    if "sangue" in t or any(k in t for k in ("hemograma", "bioquím", "t4", "sdma", "pli", "cobalamina", "b12")):
        return "sangue"
    return "outro"


def data_extenso(iso):
    d = datetime.date.fromisoformat(iso)
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def fmt(txt):
    if txt is None:
        return ""
    t = html.escape(str(txt))
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"\[\[(.+?)\]\]", r'<span class="pendente">\1</span>', t)
    return t.replace("\n", "<br>")


ICO_TEL = '<svg viewBox="0 0 24 24"><path fill="#6728BF" d="M6.6 10.8a15.5 15.5 0 0 0 6.6 6.6l2.2-2.2c.3-.3.7-.4 1-.2 1.1.4 2.3.6 3.6.6.6 0 1 .4 1 1V20c0 .6-.4 1-1 1A17 17 0 0 1 3 4c0-.6.4-1 1-1h3.5c.6 0 1 .4 1 1 0 1.3.2 2.5.6 3.6.1.3 0 .7-.2 1z"/></svg>'
ICO_MAIL = '<svg viewBox="0 0 24 24"><path fill="#6728BF" d="M3 5h18c.6 0 1 .4 1 1v12c0 .6-.4 1-1 1H3c-.6 0-1-.4-1-1V6c0-.6.4-1 1-1zm9 7.2L4.2 7v1.9L12 14l7.8-5.1V7z"/></svg>'
ICO_PIN = '<svg viewBox="0 0 24 24"><path fill="#6728BF" d="M12 2a7 7 0 0 0-7 7c0 5.2 7 13 7 13s7-7.8 7-13a7 7 0 0 0-7-7zm0 9.5A2.5 2.5 0 1 1 12 6.5a2.5 2.5 0 0 1 0 5z"/></svg>'

ICO_DOC = '<svg viewBox="0 0 24 24"><g fill="none" stroke="#6728BF" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5M8.5 12.5h7M8.5 16h4"/></g></svg>'
ICO_REG = '<svg viewBox="0 0 24 24"><g fill="none" stroke="#6728BF" stroke-width="2"><circle cx="12" cy="9" r="5"/><path d="M8.5 13l-1.5 8 5-2.5 5 2.5-1.5-8"/></g></svg>'

CAB = r"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><link rel="stylesheet" href="base.css"></head><body>
{% if atestado %}
<div class="cab at">
  <img class="logo" src="logo-vertical.png">
  <div class="div"></div>
  <div class="contato">{{ ico_tel }}{{ e.telefone }}<br>{{ ico_mail }}{{ e.email }}<br>{{ ico_pin }}São Paulo/SP</div>
  <div class="doc">{{ ico_doc }}<div class="t">Atestado de Saúde para<br>Viagens de Cães e Gatos</div></div>
</div>
{% else %}
<div class="cab">
  <img class="logo" src="logo-horizontal.png">
  <div class="contato">{{ e.telefone }} {{ ico_tel }}<br>{{ e.email }} {{ ico_mail }}<br>São Paulo/SP {{ ico_pin }}<br><span class="reg">CRMV {{ e.crmv }} · MAPA {{ e.mapa }}</span></div>
</div>
{% endif %}
<div class="cab-linha"></div>
<div class="pe"><svg viewBox="0 0 1000 80" preserveAspectRatio="none"><path fill="#6728BF" d="M0 34 C 180 0 360 62 540 38 C 720 14 860 50 1000 30 V80 H0 Z"/></svg><div class="cod">{{ a.codigo }}</div></div>
{% if not atestado %}<div class="titulo"><h1>{{ titulo }}</h1>{% if vias %}<div class="vias"><span>1ª via - <b>Farmácia</b></span><span>2ª via - <b>Paciente</b></span></div>{% endif %}</div>{% endif %}
"""

IDENT_LINHA = r"""
<div class="caixa">
Animal: <b>{{ p.nome }}</b>{% if p.id %} (ID: {{ p.id }}){% endif %}<br>
Espécie: <b>{{ p.especie }}</b>{% if p.raca %} · Raça: <b>{{ p.raca }}</b>{% endif %}{% if p.sexo %} · Sexo: <b>{{ p.sexo }}</b>{% endif %}{% if p.idade %} · Idade: <b>{{ p.idade }}</b>{% endif %}{% if p.peso %} · Peso: <b>{{ p.peso }}</b>{% endif %}{% if p.microchip %} · Microchip: <b>{{ p.microchip }}</b>{% endif %}<br>
Responsável: <b>{{ r.nome }}</b>{% if r.cpf and completo %} (CPF: {{ r.cpf }}){% endif %}
{% if r.endereco and completo %}<br>Endereço: {{ r.endereco }}{% endif %}
</div>
{% if emitente %}<div class="caixa">Emitente: <b>{{ e.nome_assinatura }}</b><br>CRMV: <b>{{ e.crmv }}</b> · Registro MAPA: <b>{{ e.mapa }}</b></div>{% endif %}
"""

IDENT_DUAS = r"""
<div class="duas">
<div class="caixa"><div class="ct">Animal</div>
{% if p.id %}<b>ID:</b> {{ p.id }}<br>{% endif %}<b>Nome:</b> {{ p.nome }}<br><b>Espécie:</b> {{ p.especie }}<br>
{% if p.raca %}<b>Raça:</b> {{ p.raca }}<br>{% endif %}{% if p.sexo %}<b>Sexo:</b> {{ p.sexo }}<br>{% endif %}
{% if p.idade %}<b>Idade:</b> {{ p.idade }}<br>{% endif %}{% if p.peso %}<b>Peso:</b> {{ p.peso }}<br>{% endif %}
{% if p.microchip %}<b>Microchip:</b> {{ p.microchip }}{% endif %}</div>
<div class="caixa"><div class="ct">Responsável</div>
<b>Nome:</b> {{ r.nome }}<br>{% if r.cpf %}<b>CPF:</b> {{ r.cpf }}<br>{% endif %}{% if r.endereco %}<b>Endereço:</b> {{ r.endereco }}{% endif %}</div>
</div>
"""

RODAPE = r"""
<div class="assin">
  <div class="data">{{ data }}</div>
  <div class="quem">{{ e.nome_assinatura }} - {{ e.titulo }}</div>
  CRMV {{ e.crmv }}<br>Registro no MAPA {{ e.mapa }}
</div></body></html>"""

RECEITA = r"""
{% for g in rx.grupos %}
<div class="via">{{ g.via }}</div>
{% for farm, itens in g.secoes %}
<div class="farm">{{ icone[farm] }} Farmácia <b>{{ farm }}</b></div>
{% for m in itens %}
<div class="med"><div class="corpo">
  <div class="topo">
    <div><div class="nomed">{{ m.nome }}</div>{% if m.apresentacao %}<div class="apres">{{ f(m.apresentacao) }}</div>{% endif %}</div>
    <div class="qtd">quantidade<b>{{ m.quantidade }}</b></div>
  </div>
  <div class="pos">{{ f(m.posologia) }}</div>
  {% if m.chips or m.alertas %}<div class="chips">{% for c in m.chips or [] %}<span class="chip">{{ c }}</span>{% endfor %}{% for c in m.alertas or [] %}<span class="chip alerta">{{ c }}</span>{% endfor %}</div>{% endif %}
</div></div>
{% endfor %}{% endfor %}{% endfor %}
{% if rx.instrucoes %}<h2>Instruções de tratamento</h2><ul class="limpa">{% for i in rx.instrucoes %}<li>{{ f(i) }}</li>{% endfor %}</ul>{% endif %}
"""

EXAMES = r"""
<p class="lead" style="margin-top:8pt">Solicito os seguintes exames para o animal acima descrito:</p>
{% for x in ex.itens %}
<div class="exame"><div class="ic">{{ icx[tipo(x)] }}</div><div>
  <div class="nomex">{{ x.nome }}</div>
  {% if x.material %}<div class="mat">Material: {{ x.material }}</div>{% endif %}
  {% if x.preparo %}<div class="prep">{{ f(x.preparo) }}</div>{% endif %}
</div></div>{% endfor %}
{% if ex.motivo %}<h2>Suspeitas / motivo</h2><ul class="limpa">{% for i in ex.motivo %}<li>{{ f(i) }}</li>{% endfor %}</ul>{% endif %}
{% if ex.observacoes %}<h2>Observações</h2><ul class="limpa">{% for i in ex.observacoes %}<li>{{ f(i) }}</li>{% endfor %}</ul>{% endif %}
{% set c = e.contatos.provet %}<div class="contatos" style="margin-top:12pt"><div class="c"><img class="lg" src="{{ c.logo }}"><div class="t">{{ c.titulo }}</div>{{ f(c.texto) }}</div></div>
{% if False %}<ul class="limpa">{% for i in ex.observacoes %}<li>{{ f(i) }}</li>{% endfor %}</ul>{% endif %}
"""

ORIENT = r"""
{% if o.saudacao %}<div class="ola">{{ o.saudacao }}</div>{% endif %}
{% if o.intro %}<p>{{ f(o.intro) }}</p>{% endif %}
{% if o.horarios %}<h2>Como dar cada medicamento</h2>
<table class="horarios"><tr><th>Medicamento</th><th>Quanto</th><th>Quando</th><th>Por quanto tempo</th></tr>
{% for h in o.horarios %}<tr><td><b>{{ h.med }}</b></td><td>{{ f(h.dose) }}</td><td>{{ f(h.quando) }}</td><td>{{ f(h.duracao) }}</td></tr>{% endfor %}</table>{% endif %}
{% for s in o.secoes or [] %}<h2>{{ s.titulo }}</h2>
<div class="{{ {'alerta':'alerta-box','nota':'nota'}.get(s.tipo, '') }}">{% if s.texto %}<p>{{ f(s.texto) }}</p>{% endif %}
{% if s.itens %}<ul class="limpa">{% for i in s.itens %}<li>{{ f(i) }}</li>{% endfor %}</ul>{% endif %}
{% if s.produtos %}<div class="nutri">{% for pr in s.produtos %}<div class="np">{% if pr.foto %}<img src="{{ pr.foto }}">{% endif %}<div class="nn">{{ pr.nome }}</div>{% if pr.obs %}<div class="no">{{ f(pr.obs) }}</div>{% endif %}</div>{% endfor %}</div>{% endif %}</div>{% endfor %}
<h2>Contatos úteis</h2>
<div class="contatos">
{% for k in contatos %}{% set c = e.contatos[k] %}<div class="c">{% if c.logo %}<img class="lg" src="{{ c.logo }}">{% endif %}<div class="t">{{ c.titulo }}</div>{{ f(c.texto) }}{% if c.cupom %}<br><span class="cupom">{{ f(c.cupom) }}</span>{% endif %}</div>{% endfor %}
</div>
"""


ATESTADO = r"""
<style>.cel{padding:2.6pt 8pt;font-size:8.4pt}.cel .r{font-size:6.6pt}.sec{margin:5pt 0 3pt}.linha{margin-bottom:3pt}.texto-fixo{font-size:8.3pt;padding:6pt 10pt}.titulo{margin-bottom:4pt}.assin-at{margin-top:8pt}.assin-at .ac .esp{height:14pt}.sec .n{width:15pt;height:15pt;line-height:15pt}</style>
<div class="sec"><span class="n">1</span><span class="t">Identificação do tutor</span></div>
<div class="linha"><div class="cel"><span class="r">Nome completo</span><span class="v">{{ t.nome }}</span></div></div>
<div class="linha"><div class="cel"><span class="r">CPF / passaporte</span><span class="v">{{ t.documento }}</span></div><div class="cel"><span class="r">Telefone</span><span class="v">{{ t.telefone }}</span></div></div>
<div class="linha"><div class="cel" style="flex:2.2"><span class="r">Endereço</span><span class="v">{{ t.endereco }}</span></div><div class="cel"><span class="r">Cidade/UF</span><span class="v">{{ t.cidade_uf }}</span></div></div>

<div class="sec"><span class="n">2</span><span class="t">Identificação do animal</span></div>
<div class="linha"><div class="cel" style="flex:1.6"><span class="r">Nome</span><span class="v">{{ p.nome }}</span></div><div class="cel"><span class="r">Espécie</span><span class="v">{{ p.especie }}</span></div>
<div class="cel"><span class="r">Sexo</span><span class="cx {{ 'on' if p.sexo|lower in ('fêmea','femea') }}"></span>fêmea<span class="cx {{ 'on' if p.sexo|lower == 'macho' }}"></span>macho</div></div>
<div class="linha"><div class="cel"><span class="r">Raça</span><span class="v">{{ p.raca }}</span></div><div class="cel"><span class="r">Pelagem</span><span class="v">{{ an.pelagem }}</span></div><div class="cel"><span class="r">Nascimento</span><span class="v">{{ an.nascimento }}</span></div></div>
<div class="linha"><div class="cel"><span class="r">Porte</span><span class="v">{{ an.porte }}</span></div><div class="cel" style="flex:1.6"><span class="r">Microchip</span><span class="v">{{ p.microchip }}</span></div><div class="cel"><span class="r">Aplicação do microchip</span><span class="v">{{ an.aplicacao_microchip }}</span></div></div>

<div class="sec"><span class="n">3</span><span class="t">Vacina antirrábica</span></div>
<div class="linha"><div class="cel"><span class="r">Laboratório</span><span class="v">{{ v.laboratorio }}</span></div><div class="cel"><span class="r">Nome comercial</span><span class="v">{{ v.nome_comercial }}</span></div></div>
<div class="linha"><div class="cel"><span class="r">Aplicação</span><span class="v">{{ v.aplicacao }}</span></div><div class="cel"><span class="r">Validade</span><span class="v">{{ v.validade }}</span></div><div class="cel"><span class="r">Lote</span><span class="v">{{ v.lote }}</span></div></div>
<div class="mini">*para viagens à União Europeia é necessário anexar laudo sorológico conforme Regulamento (UE) 576/2013.</div>

<div class="sec"><span class="n">4</span><span class="t">Informações sanitárias</span></div>
<div class="texto-fixo">Atesto para os devidos fins que o animal acima identificado, foi por mim examinado, está clinicamente sadio, não apresenta sinais de doenças infectocontagiosas e parasitárias, inclusive livre da presença de miíases, e até onde alcança meu conhecimento não foi diagnosticado positivamente para leishmaniose, portanto está apto para o transporte.</div>

<div class="sec"><span class="n">5</span><span class="t">Antiparasitários</span></div>
{% for rot, x in [('interno', at.antiparasitario_interno), ('externo', at.antiparasitario_externo)] %}
<div class="grupo"><div class="lado"><span>{{ rot }}</span></div><div class="campos">
<div class="linha"><div class="cel"><span class="r">Aplicação</span><span class="v">{{ x.aplicacao }}</span></div><div class="cel" style="flex:1.6"><span class="r">Laboratório</span><span class="v">{{ x.laboratorio }}</span></div></div>
<div class="linha"><div class="cel"><span class="r">Nome comercial</span><span class="v">{{ x.nome_comercial }}</span></div><div class="cel" style="flex:1.6"><span class="r">Princípios ativos</span><span class="v">{{ x.principios }}</span></div></div>
</div></div>{% endfor %}
<div class="mini">Aplicados dentro dos 15 (quinze) dias anteriores à emissão do CVI no caso de viagens ao Mercosul.</div>

<div class="sec"><span class="n">6</span><span class="t">Informações adicionais</span><span class="dir">inutilizar este campo caso não seja necessário</span></div>
<div class="texto-fixo" style="min-height:16pt">{{ f(at.adicionais) }}</div>

<div class="assin-at"><div><b>São Paulo, {{ data }}</b></div>
<div class="ac">Assinatura e carimbo:<div class="esp"></div><b>{{ e.nome_assinatura }} - {{ e.titulo }}</b><br>CRMV {{ e.crmv }} · Registro no MAPA {{ e.mapa }}</div></div>
</body></html>"""


GUIA = r"""
{% if g.destaque %}<div class="hero"><div class="h">{{ g.destaque }}</div>{% if g.para %}<div class="para">{{ g.para }}</div>{% endif %}</div>{% endif %}
{% set n = namespace(i=0) %}
{% if en %}{% set n.i = n.i + 1 %}
<div class="sec"><span class="n">{{ n.i }}</span><span class="t">Necessidade energética diária</span></div>
{% if g.energia.texto %}<p>{{ f(g.energia.texto) }}</p>{% endif %}
<div class="stats">
 <div class="st"><div class="r">Peso atual</div><div class="v">{{ en.peso }}<small> kg</small></div></div>
 <div class="st"><div class="r">RER (repouso)</div><div class="v">{{ en.rer }}<small> kcal</small></div></div>
 <div class="st"><div class="r">{{ g.energia.rotulo_der or 'DER (diário)' }}</div><div class="v">~{{ en.der }}<small> kcal/dia</small></div></div>
 <div class="st"><div class="r">Refeições/dia</div><div class="v">{{ en.ref }}x<small> ~{{ en.porref }} kcal cada</small></div></div>
</div>{% endif %}
{% if tabs %}{% set n.i = n.i + 1 %}
<div class="sec"><span class="n">{{ n.i }}</span><span class="t">{{ g.racoes.titulo or 'Opções de ração' }}</span></div>
{% if g.racoes.texto %}<p>{{ f(g.racoes.texto) }}</p>{% endif %}
{% for tb in tabs %}
<div class="marca"><div class="ml">{% if tb.logo %}<img class="lgm" src="{{ tb.logo }}">{% endif %}<span>{{ tb.nomes }}</span></div>
<div class="fotos">{% for fo in tb.fotos %}<div><img src="{{ fo.src }}"><span>{{ fo.rot }}</span></div>{% endfor %}</div></div>
<table class="rac"><tr><th>Opção</th><th>Composição</th><th class="dir">Quantidade/dia</th><th class="dir">Por refeição ({{ en.ref }}x)</th></tr>
{% for l in tb.linhas %}<tr><td><span class="tag {{ l.tipo }}">{{ l.rotulo }}</span></td><td>{{ l.comp }}<div class="sub">{{ l.sub }}</div></td><td class="dir q">{{ l.dia }}</td><td class="dir">{{ l.ref }}</td></tr>{% endfor %}
</table>{% endfor %}
{% for nt in g.racoes.notas or [] %}<div class="{{ 'alerta-box' if nt.tipo == 'alerta' else 'nota' }} gap">{{ f(nt.texto) }}</div>{% endfor %}
{% endif %}
{% for s in g.secoes or [] %}{% set n.i = n.i + 1 %}
<div class="sec"><span class="n">{{ n.i }}</span><span class="t">{{ s.titulo }}</span></div>
{% if s.texto %}<p>{{ f(s.texto) }}</p>{% endif %}
{% if s.itens %}<ul class="limpa {{ 'duas-col' if s.colunas == 2 }}">{% for i in s.itens %}<li>{{ f(i) }}</li>{% endfor %}</ul>{% endif %}
{% if s.nota %}<div class="{{ 'alerta-box' if s.nota.tipo == 'alerta' else 'nota' }} gap">{{ f(s.nota.texto) }}</div>{% endif %}
{% endfor %}
"""


def preparar_receita(a, catalogo, conferencia):
    rx = a["receita"]
    peso = a["paciente"].get("peso_kg")
    for g in rx["grupos"]:
        secoes = {}
        for m in g["itens"]:
            prod = catalogo.get(m.get("produto"), {}) if m.get("produto") else {}
            for campo in ("nome", "apresentacao", "farmacia", "foto"):
                m.setdefault(campo, prod.get(campo))
            if m.get("foto"):
                m["foto"] = str((AQUI / "catalogo" / "fotos" / m["foto"]).resolve())
            if "calculo" in m:
                c = m["calculo"]
                base = {**prod, **c.get("produto_override", {})}
                if not peso:
                    conferencia.append(f"{m['nome']}: sem peso informado, cálculo não feito.")
                    m.setdefault("posologia", "[[posologia: falta o peso]]")
                else:
                    r = calcular(peso, c["dose_mg_kg"], base, c["freq_h"], c.get("dias"),
                                 c.get("continuo", False), c.get("se_necessario", False))
                    m["posologia"] = r["posologia"]
                    conferencia.append(f"{m['nome']} ({c['dose_mg_kg']} mg/kg decidido)")
                    conferencia += ["  " + l for l in r["memoria"]]
                    conferencia += ["  ATENÇÃO: " + x for x in r["alertas"]]
            secoes.setdefault(m.get("farmacia") or "veterinária", []).append(m)
        g["secoes"] = sorted(secoes.items(), key=lambda kv: ORDEM_FARM.index(kv[0]) if kv[0] in ORDEM_FARM else 9)
    return rx


def main():
    src = Path(sys.argv[1])
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else src.parent
    out.mkdir(parents=True, exist_ok=True)
    a = json.loads(src.read_text(encoding="utf-8"))
    e = json.loads((AQUI / "emitente.json").read_text(encoding="utf-8"))
    catalogo = json.loads((AQUI / "catalogo" / "produtos.json").read_text(encoding="utf-8"))
    env = Environment(loader=BaseLoader(), autoescape=False)
    ctx = dict(ico_doc=ICO_DOC, ico_reg=ICO_REG, ico_tel=ICO_TEL, ico_mail=ICO_MAIL, ico_pin=ICO_PIN, e=e, a=a, p=a["paciente"], r=a["responsavel"], data=data_extenso(a["data"]), f=fmt, icone=ICONE)
    conferencia = []
    docs = []
    if "receita" in a:
        rx = preparar_receita(a, catalogo, conferencia)
        ctl = rx.get("controle_especial", False)
        corpo = env.from_string(IDENT_LINHA).render(completo=True, emitente=True, **ctx) + env.from_string(RECEITA).render(rx=rx, **ctx)
        docs.append(("receita", "Receita de controle especial" if ctl else "Receita simples", ctl, corpo))
    if "exames" in a:
        corpo = env.from_string(IDENT_LINHA).render(completo=True, emitente=False, **ctx) + env.from_string(EXAMES).render(ex=a["exames"], icx=EXAME_ICONE, tipo=tipo_exame, **ctx)
        docs.append(("exames", "Solicitação de exames", False, corpo))
    if "orientacoes" in a:
        o = a["orientacoes"]
        tem_manip = any(m.get("farmacia") == "manipulação" for g in a.get("receita", {}).get("grupos", []) for m in g["itens"])
        contatos = ["petz", "provet"] + (["manipulacao"] if tem_manip or o.get("mostrar_manipulacao") else [])
        corpo = env.from_string(IDENT_LINHA).render(completo=True, emitente=False, **ctx) + env.from_string(ORIENT).render(o=o, contatos=contatos, **ctx)
        docs.append(("orientacoes", "Orientações para casa", False, corpo))
    if "guia" in a:
        from nutri import energia, opcoes
        from calc import br
        g = a["guia"]
        alim = json.loads((AQUI / "catalogo" / "alimentos.json").read_text(encoding="utf-8"))
        peso = a["paciente"].get("peso_kg")
        en, tabs = None, []
        if g.get("energia"):
            ge = g["energia"]
            r, d, mem = energia(peso, ge.get("fator"), ge.get("der"))
            ref = ge["refeicoes"]
            en = dict(peso=br(peso), rer=round(r), der=round(d), ref=ref, porref=round(d / ref))
            conferencia.append("Prescrição nutricional"); conferencia += ["  " + x for x in mem]
            for par in g.get("racoes", {}).get("marcas", []):
                seca = alim.get(par.get("seca")); umida = alim.get(par.get("umida"))
                linhas, m2 = opcoes(d, ref, seca, umida, g["racoes"].get("pct_seca_mix", 0.9))
                conferencia += ["  " + x for x in m2]
                mk = alim["_marcas"].get((seca or umida)["marca"], {})
                fotos = [dict(src=str(AQUI / "catalogo" / "fotos" / x["foto"]), rot=x["formato"].capitalize()) for x in (seca, umida) if x and x.get("foto")]
                tabs.append(dict(logo=str(AQUI / "catalogo" / "fotos" / mk["logo"]) if mk.get("logo") else None,
                                 nomes=" · ".join(f"{x['nome']} ({x['formato']})" for x in (seca, umida) if x), fotos=fotos, linhas=linhas))
        corpo = env.from_string(IDENT_LINHA).render(completo=True, emitente=False, **ctx) + env.from_string(GUIA).render(g=g, en=en, tabs=tabs, **ctx)
        docs.append(("guia-alimentar", g.get("titulo_doc", "Guia alimentar"), False, corpo))
    if "atestado" in a:
        at = a["atestado"]
        corpo = env.from_string(ATESTADO).render(at=at, t=at["tutor"], an=at.get("animal", {}), v=at["vacina"], **ctx)
        docs.append(("atestado", "Atestado de saúde para viagem", "sem_rodape", corpo))
    for nome, titulo, vias, corpo in docs:
        if vias == "sem_rodape":
            page = env.from_string(CAB).render(titulo=titulo, vias=False, atestado=True, **ctx) + corpo
            destino = out / f"{a.get('codigo', 'atendimento')}_{nome}.pdf"
            HTML(string=page, base_url=str(AQUI)).write_pdf(destino)
            print(destino)
            continue
        page = env.from_string(CAB).render(titulo=titulo, vias=vias, atestado=False, **ctx) + corpo + env.from_string(RODAPE).render(**ctx)
        destino = out / f"{a.get('codigo', 'atendimento')}_{nome}.pdf"
        HTML(string=page, base_url=str(AQUI)).write_pdf(destino)
        print(destino)
    if conferencia:
        (out / f"{a.get('codigo', 'atendimento')}_conferencia.txt").write_text("\n".join(conferencia), encoding="utf-8")
        print("\n".join(conferencia))


if __name__ == "__main__":
    main()
