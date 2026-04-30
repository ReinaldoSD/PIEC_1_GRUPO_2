from flask import jsonify, request, render_template
from banco_dados.database import conectar, cadastrar_roupa, editar_roupa, excluir_roupa
from datetime import datetime
from werkzeug.utils import secure_filename
import os
import json
from google import genai
from google.genai import types
import PIL.Image
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=API_KEY)

def configure_routes(app):
    @app.route('/')
    def home():
        return render_template("index.html")

    @app.route('/listar')
    def listar():
        conn = conectar()
        cursor = conn.cursor()
        
        # 1. Primeiro, pegamos todas as roupas
        cursor.execute("SELECT * FROM roupas")
        roupas = [dict(row) for row in cursor.fetchall()]
        
        # 2. Agora, para cada roupa, vamos buscar as suas fotos associadas
        for roupa in roupas:
            cursor.execute("SELECT caminho FROM fotos_roupas WHERE roupa_id = ?", (roupa['id'],))
            # Criamos uma lista de fotos dentro de cada objeto de roupa
            fotos = [row['caminho'] for row in cursor.fetchall()]
            # Se a roupa tiver fotos, guardamos a lista. Se não, enviamos uma lista vazia.
            roupa['fotos'] = fotos
        
        conn.close()
        return jsonify(roupas)

    @app.route('/usar/<int:roupa_id>')
    def usar(roupa_id):
        conn = conectar()
        cursor = conn.cursor()
        cursor.execute("UPDATE roupas SET vezes_usada = vezes_usada + 1 WHERE id = ?", (roupa_id,))
        data_atual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("INSERT INTO historico (roupa_id, data_uso) VALUES (?, ?)", (roupa_id, data_atual))
        conn.commit()
        conn.close()
        return f"Roupa {roupa_id} usada em {data_atual}!"

    @app.route('/historico')
    def historico():
        conn = conectar()
        cursor = conn.cursor()
        # Usamos o JOIN para conectar a tabela 'historico' com a 'roupas'
        # Assim temos acesso ao 'nome' da peça
        cursor.execute("""
            SELECT h.data_uso, r.nome 
            FROM historico h
            JOIN roupas r ON h.roupa_id = r.id
            ORDER BY h.id DESC
        """)
        dados = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return jsonify(dados)

    @app.route('/excluir/<int:roupa_id>')
    def excluir(roupa_id):
        # O nome devolvido pelo database.py é guardado nesta variável
        nome_da_peca = excluir_roupa(roupa_id)
        
        # Agora montamos uma mensagem bonita e amigável para o utilizador!
        return f"A peça '{nome_da_peca}' foi excluída com sucesso!"
    
    @app.route('/cadastrar_via_imagem', methods=['POST'])
    def cadastrar_via_imagem():
        files = request.files.getlist('imagem') # Aceita várias fotos!
        if not files or files[0].filename == '':
            return jsonify({"erro": "Nenhuma imagem enviada"}), 400

        caminhos_temp = []
        imagens_ia = ["""Analise estas fotos da mesma roupa e retorne APENAS um JSON válido.
                                Restrinja as respostas às seguintes categorias:
                                {
                                    "nome": "Crie um nome curto", 
                                    "tipo": "Escolha entre: Camisa, Calça, Casaco, Calçado, Acessório", 
                                    "cor": "Cor predominante", 
                                    "ocasiao": "Escolha entre: Trabalho, Casual, Festa, Esporte", 
                                    "clima_ideal": "Escolha entre: Quente, Frio, Meia-estação"
                                }"""]

        try:
            upload_dir = os.path.join(app.root_path, 'static', 'uploads')
            os.makedirs(upload_dir, exist_ok=True)

            for file in files:
                filename = secure_filename(file.filename)
                path = os.path.join(upload_dir, filename)
                file.save(path)
                caminhos_temp.append(f"static/uploads/{filename}")
                imagens_ia.append(PIL.Image.open(path))

            # Chama a IA
            response = client.models.generate_content(
                model='gemini-2.5-flash', # Use a versão disponível
                contents=imagens_ia,
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            
            return jsonify({
                "dados": json.loads(response.text),
                "caminhos": caminhos_temp
            }), 200
        except Exception as e:
            return jsonify({"erro": str(e)}), 500

    @app.route('/salvar_final', methods=['POST'])
    def salvar_final():
        dados = request.json
        cadastrar_roupa(
            dados['nome'], dados['tipo'], dados['cor'], 
            dados['ocasiao'], dados['clima'], dados['caminhos']
        )
        return jsonify({"mensagem": "Roupa guardada no armário com sucesso!"})