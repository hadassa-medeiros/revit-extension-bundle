pyRevit extension composed by multipurpose tools focused on model geometry and report generation.

## Estrutura

- `HMCustomTools.extension`: extensao instalada pelo pyRevit.
- `Relatórios.panel/Contagem Temática.pushbutton`: botao exibido no Revit.
- `HMCustomTools.extension/lib/count_by_theme.py`: logica testavel de filtragem.
- `tests`: testes unitarios sem dependencia da API do Revit.

## Testes

Na raiz do projeto:

```powershell
python -m unittest discover -s tests -v
```

## Instalar no pyRevit

Adicione a pasta como clone/extensao no pyRevit. O pyRevit reconhece a pasta `HMCustomTools.extension` e cria a aba, painel e botao automaticamente.
