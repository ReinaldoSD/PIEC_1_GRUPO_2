from flask import jsonify, request, render_template, redirect, session, url_for
from banco_dados.database import conectar, cadastrar_roupa, editar_roupa, excluir_roupa
from datetime import datetime
import os, json, uuid, io, base64
from PIL import Image
from collections import Counter
import torch
from transformers import CLIPProcessor, CLIPModel

# ==========================================
# CONFIGURAÇÃO DA IA LOCAL (DENTRO DA PASTA INSTANCE)
# ==========================================
print(" Carregando IA Local (CLIP - Alta Precisão)...")
device = "cuda" if torch.cuda.is_available() else "cpu"

# Caminho dentro da pasta instance (cria se não existir)
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_PATH = os.path.join(BASE_DIR, 'instance')
MODELO_LOCAL_PATH = os.path.join(INSTANCE_PATH, 'clip-vit-base-patch32')
modelo_id = "openai/clip-vit-base-patch32"

# Garante que a pasta instance existe
os.makedirs(INSTANCE_PATH, exist_ok=True)

# Verifica se o modelo já está salvo na pasta instance
if os.path.exists(MODELO_LOCAL_PATH):
    print(" Modelo encontrado na pasta instance — carregando sem acesso à internet...")
    try:
        modelo = CLIPModel.from_pretrained(MODELO_LOCAL_PATH, local_files_only=True).to(device)
        processador = CLIPProcessor.from_pretrained(MODELO_LOCAL_PATH, local_files_only=True)
    except Exception as e:
        print(f" Erro ao carregar modelo local: {e}")
        print(" Tentando baixar novamente...")
        modelo = CLIPModel.from_pretrained(modelo_id).to(device)
        processador = CLIPProcessor.from_pretrained(modelo_id)
        modelo.save_pretrained(MODELO_LOCAL_PATH)
        processador.save_pretrained(MODELO_LOCAL_PATH)
else:
    print(" Modelo não encontrado na pasta instance — baixando pela primeira vez...")
    modelo = CLIPModel.from_pretrained(modelo_id).to(device)
    processador = CLIPProcessor.from_pretrained(modelo_id)
    modelo.save_pretrained(MODELO_LOCAL_PATH)
    processador.save_pretrained(MODELO_LOCAL_PATH)
    print(" Modelo salvo com sucesso em: ", MODELO_LOCAL_PATH)

# ==========================================
# CATEGORIAS, MAPEAMENTOS E PESOS
# ==========================================
CATEGORIAS_IA = {
    "tipo": [
        "camiseta básica", "camiseta gola polo", "camiseta regata",
        "camisa social manga curta", "camisa social manga longa", "camisa de linho", "camisa xadrez",
        "blusa solta", "blusa de alcinha", "blusa manga comprida",
        "suéter de lã", "cardigã", "moletom com capuz", "moletom liso",
        "jaqueta jeans", "jaqueta de couro", "jaqueta corta vento", "jaqueta de lã",
        "casaco grosso", "casaco leve", "paletó", "blazer", "terno completo", "colete",
        "calça jeans", "calça social", "calça linho", "calça sarja", "calça moletom", "calça de alfaiataria",
        "bermuda jeans", "bermuda linho", "bermuda de tecido", "bermuda moletom",
        "saia curta", "saia longa", "saia plissada", "saia lápis", "saia jeans",
        "vestido curto", "vestido longo", "vestido midi", "vestido de festa", "vestido casual",
        "macacão curto", "macacão longo", "macacão jeans", "macacão de tecido",
        "macaquinho", "conjunto de duas peças", "roupa de banho", "roupa íntima",
        "cachecol", "lenço", "chapéu", "boné", "luva", "meia grossa", "meia fina"
    ],
    "cor": [
        "predominantemente branca",
        "predominantemente preta",
        "predominantemente cinza clara",
        "predominantemente cinza escura",
        "predominantemente azul clara",
        "predominantemente azul marinho",
        "predominantemente azul jeans",
        "predominantemente vermelha",
        "predominantemente vinho",
        "predominantemente rosa",
        "predominantemente amarela",
        "predominantemente laranja",
        "predominantemente verde clara",
        "predominantemente verde escura",
        "predominantemente marrom",
        "predominantemente bege",
        "predominantemente creme",
        "predominantemente roxa",
        "predominantemente lilás",
        "estampada floral",
        "estampada listrada",
        "estampada xadrez",
        "estampada geométrica",
        "colorida sem cor predominante",
        "várias cores sem dominância"
    ],
    "clima_ideal": [
        "roupa para calor",
        "roupa para frio",
        "roupa para meia estação"
    ],
    "ocasiao": [
        "uso casual",
        "uso trabalho",
        "uso festa",
        "uso esporte",
        "uso passeio"
    ]
}

MAPEAMENTO_CLIMA = {
    "roupa para calor": "Calor",
    "roupa para frio": "Frio",
    "roupa para meia estação": "Meia-Estação"
}

MAPEAMENTO_COR = {
    "predominantemente branca": "Branca",
    "predominantemente preta": "Preta",
    "predominantemente cinza clara": "Cinza Clara",
    "predominantemente cinza escura": "Cinza Escura",
    "predominantemente azul clara": "Azul Clara",
    "predominantemente azul marinho": "Azul Marinho",
    "predominantemente azul jeans": "Azul Jeans",
    "predominantemente vermelha": "Vermelha",
    "predominantemente vinho": "Vinho",
    "predominantemente rosa": "Rosa",
    "predominantemente amarela": "Amarela",
    "predominantemente laranja": "Laranja",
    "predominantemente verde clara": "Verde Clara",
    "predominantemente verde escura": "Verde Escura",
    "predominantemente marrom": "Marrom",
    "predominantemente bege": "Bege",
    "predominantemente creme": "Creme",
    "predominantemente roxa": "Roxa",
    "predominantemente lilás": "Lilás",
    "estampada floral": "Estampa Floral",
    "estampada listrada": "Listrada",
    "estampada xadrez": "Xadrez",
    "estampada geométrica": "Estampa Geométrica",
    "colorida sem cor predominante": "Colorida",
    "várias cores sem dominância": "Multicolorida"
}

PESOS = {
    "tipo": 1.5,
    "cor": 1.2,
    "clima_ideal": 1.3,
    "ocasiao": 1.0
}

# ==========================================
# FUNÇÃO DE ANÁLISE LOCAL
# ==========================================
def analisar_localmente(imagens_pil):
    votos = {k: [] for k in CATEGORIAS_IA.keys()}
    confianca_total = []

    for img in imagens_pil:
        for chave, labels in CATEGORIAS_IA.items():
            inputs = processador(
                text=labels,
                images=img,
                return_tensors="pt",
                padding=True,
                truncation=True
            ).to(device)

            with torch.no_grad():
                outputs = modelo(**inputs)

            probs = outputs.logits_per_image.softmax(dim=1)[0]
            probs = probs * PESOS[chave]
            probs = probs / probs.sum()

            idx_vencedor = torch.argmax(probs).item()
            vencedor = labels[idx_vencedor]
            confianca = round(probs[idx_vencedor].item() * 100, 2)
            confianca_total.append(confianca)

            if chave == "tipo":
                limpo = vencedor
            elif chave == "cor":
                limpo = MAPEAMENTO_COR.get(vencedor, vencedor)
            elif chave == "clima_ideal":
                limpo = MAPEAMENTO_CLIMA.get(vencedor, "Meia-Estação")
            elif chave == "ocasiao":
                limpo = vencedor.replace("uso ", "")

            votos[chave].append(limpo)

    tipo_vencedor = Counter(votos['tipo']).most_common(1)[0][0].title()
    cor_vencedora = Counter(votos['cor']).most_common(1)[0][0]
    clima_vencedor = Counter(votos['clima_ideal']).most_common(1)[0][0]
    ocasiao_vencedora = Counter(votos['ocasiao']).most_common(1)[0][0].title()
    confianca_media = round(sum(confianca_total) / len(confianca_total), 2)

    nome_estetico = f"{tipo_vencedor} {cor_vencedora}"
    descricao = (
        f"Peça identificada como {tipo_vencedor}, cor {cor_vencedora.lower()}. "
        f"Ideal para {clima_vencedor.lower()} e uso {ocasiao_vencedora.lower()}."
    )

    return {
        "nome": nome_estetico,
        "tipo": tipo_vencedor,
        "cor": cor_vencedora,
        "clima": clima_vencedor,
        "ocasiao": ocasiao_vencedora,
        "confianca": f"{confianca_media}%",
        "descricao": descricao
    }

# ==========================================
# ROTAS COMPLETAS
# ==========================================
def configure_routes(app):

    @app.route('/')
    def home():
        return redirect('/dashboard')

    @app.route('/dashboard')
    def dashboard():
        session['usuario_id'] = 1
        session['usuario_nome'] = "Admin"

        conn = conectar()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) as total FROM roupas")
        total_roupas = cursor.fetchone()['total']

        cursor.execute("SELECT * FROM roupas ORDER BY vezes_usada ASC LIMIT 5")
        menos_usadas = cursor.fetchall()
        conn.close()

        return render_template(
            'dashboard.html',
            total_roupas=total_roupas,
            menos_usadas=menos_usadas
        )

    @app.route('/cadastrar')
    def cadastrar_page():
        return render_template('cadastrar_roupa.html')

    @app.route('/roupas')
    def roupas_page():
        return render_template('minhas_roupas.html')

    @app.route('/historico_page')
    def historico_page():
        return render_template('historico.html')

    @app.route('/cadastrar_via_imagem', methods=['POST'])
    def cadastrar_via_imagem():
        files = request.files.getlist('imagem')
        if not files or files[0].filename == '':
            return jsonify({"erro": "Nenhuma imagem enviada"}), 400

        imagens_pil = []
        fotos_base64 = []

        try:
            for file in files:
                img_bytes = file.read()
                img_pil = Image.open(io.BytesIO(img_bytes)).convert("RGB")
                imagens_pil.append(img_pil)

                encoded = base64.b64encode(img_bytes).decode('utf-8')
                ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else 'jpeg'
                fotos_base64.append(f"data:image/{ext};base64,{encoded}")

            # Análise feita com IA Local
            dados_ia = analisar_localmente(imagens_pil)

            return jsonify({
                "dados": dados_ia,
                "fotos_base64": fotos_base64
            }), 200

        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({"erro": str(e)}), 500

    @app.route('/salvar_final', methods=['POST'])
    def salvar_final():
        dados = request.json
        fotos_base64 = dados.get('fotos_base64', [])
        caminhos_finais = []
        upload_dir = os.path.join(app.root_path, 'static', 'uploads')
        os.makedirs(upload_dir, exist_ok=True)

        for data_uri in fotos_base64:
            header, encoded = data_uri.split(",", 1)
            ext = header.split("/")[1].split(";")[0]
            nome_arquivo = f"{uuid.uuid4().hex}.{ext}"
            path_completo = os.path.join(upload_dir, nome_arquivo)
            with open(path_completo, "wb") as f:
                f.write(base64.b64decode(encoded))
            caminhos_finais.append(f"static/uploads/{nome_arquivo}")

        cadastrar_roupa(
            dados.get('nome'),
            dados.get('tipo'),
            dados.get('cor'),
            dados.get('ocasiao'),
            dados.get('clima'),
            caminhos_finais
        )
        return jsonify({"mensagem": "Roupa guardada com sucesso!"}), 200

    @app.route('/listar')
    def listar():
        nome = request.args.get('nome', '').lower()
        tipo = request.args.get('tipo', '')
        cor = request.args.get('cor', '')

        conn = conectar()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM roupas")
        roupas = {row['id']: dict(row) for row in cursor.fetchall()}
        
        for r in roupas.values():
            r['fotos'] = []

        cursor.execute("SELECT roupa_id, caminho FROM fotos_roupas")
        for row in cursor.fetchall():
            if row['roupa_id'] in roupas:
                roupas[row['roupa_id']]['fotos'].append(row['caminho'])

        conn.close()
        lista = list(roupas.values())

        if nome: lista = [r for r in lista if nome in r['nome'].lower()]
        if tipo: lista = [r for r in lista if r['tipo'] == tipo]
        if cor: lista = [r for r in lista if r['cor'] == cor]

        return jsonify(lista)

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        return redirect('/dashboard')

    @app.route('/register')
    def register_page():
        return redirect('/dashboard')

    @app.route('/registrar', methods=['POST'])
    def registrar():
        return redirect('/dashboard')
        
    @app.route('/excluir/<int:roupa_id>')
    def excluir(roupa_id):
        nome_da_peca = excluir_roupa(roupa_id)
        return f"A peça '{nome_da_peca}' foi excluída!"

    @app.route('/usar/<int:roupa_id>')
    def usar(roupa_id):
        conn = conectar()
        cursor = conn.cursor()
        cursor.execute("UPDATE roupas SET vezes_usada = vezes_usada + 1 WHERE id = ?", (roupa_id,))
        data_atual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("INSERT INTO historico (roupa_id, data_uso) VALUES (?, ?)", (roupa_id, data_atual))
        conn.commit()
        conn.close()
        return "ok"

    
    @app.route('/historico')
    def historico():
        conn = conectar()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT h.data_uso, r.nome 
            FROM historico h
            JOIN roupas r ON h.roupa_id = r.id
            ORDER BY h.id DESC
        """)
        dados = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return jsonify(dados)
