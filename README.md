# Label Studio YOLO

Aplicativo desktop em Python para anotar imagens localmente e exportar caixas e polígonos no formato YOLO.

## Requisitos

- Python 3.10 ou superior
- Tkinter (incluído nas distribuições padrão do Python para Windows)

## Instalação e execução

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m labeler
```

## Uso

1. Clique em **Abrir pasta** e escolha a pasta com as imagens.
2. Selecione uma classe ou cadastre outra no painel da direita. A classe selecionada será usada nos novos labels; para mudar a classe de um label existente, selecione-o na lista de anotações e clique em **Alterar classe do label selecionado**. Os nomes ficam em `classes.txt` e os IDs YOLO correspondem à ordem das linhas, começando em zero.
3. Escolha **Retângulo** e arraste para criar uma caixa; escolha **Polígono**, clique nos vértices e pressione Enter para concluir.
4. Em **Selecionar**, arraste o interior para mover uma anotação; arraste as alças para redimensionar a caixa ou ajustar vértices. Use Delete para excluir.
5. Use a roda do mouse para zoom no cursor, os botões `+`/`−` para zoom centralizado e o botão do meio do mouse para mover a imagem.
6. As anotações são salvas automaticamente ao editar e ao trocar de imagem. Também é possível usar Ctrl+S.

Os arquivos de imagem permanecem intactos. Os rótulos são gravados em `labels/<nome-da-imagem>.txt` dentro da pasta selecionada. Caixas usam o formato YOLO de detecção (`classe x_centro y_centro largura altura`); polígonos usam o formato YOLO de segmentação (`classe x1 y1 x2 y2 ...`). Todas as coordenadas são normalizadas pela largura e altura originais da imagem.

## Testes

```powershell
python -m unittest discover -s tests
```

## Estrutura

```text
labeler/
  app.py       Interface e fluxo da aplicação
  canvas.py    Visualização, zoom, desenho e edição
  images.py    Descoberta de imagens suportadas
  models.py    Modelo de anotação
  yolo.py      Leitura e gravação de labels YOLO
  __main__.py  Inicialização do aplicativo
tests/
  test_yolo.py Testes de serialização YOLO
```
