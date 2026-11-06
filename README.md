# Assistente Clínico: kit de documentos

Gerador dos documentos do Dellatorre Vet: anamnese, receita, solicitação de exames, orientações, atestado e guia alimentar.

- `render.py`: gera os PDFs a partir de um JSON de atendimento.
- `calc.py`: cálculo de dose. `nutri.py`: cálculo energético e de rações.
- `base.css`, `fonts/`, `*.png`: identidade visual.
- `emitente.json`: dados do emitente e contatos.
- `catalogo/`: produtos e alimentos cadastrados.
- `exemplo*.json`: atendimentos fictícios para teste.
- `instrucoes-assistente-clinico.md`: instruções do Project.

Uso: `python3 render.py atendimento.json pasta_saida`

Fotos de produtos ainda não foram adicionadas à receita. Não commitar dados reais de paciente.
