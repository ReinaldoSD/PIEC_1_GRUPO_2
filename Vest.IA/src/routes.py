from flask import jsonify, request, render_template, redirect, session, url_for, flash
from banco_dados.database import (
    conectar, cadastrar_roupa, editar_roupa, excluir_roupa, 
    cadastrar_usuario, verificar_usuario, email_existe, buscar_historico_usuario
)
from datetime import datetime
import os, uuid, io, base64, random, smtplib, sqlite3, requests
from email.mime.text import MIMEText
from PIL import Image
from collections import Counter
import torch
from transformers import CLIPProcessor, CLIPModel
from werkzeug.security import generate_password_hash
from functools import wraps

# CAMINHOS BASE
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# CONFIGURAÇÃO IA LOCAL (FASHION-CLIP) 
device = "cuda" if torch.cuda.is_available() else "cpu"
MODELO_PATH = os.path.join(BASE_DIR, 'instance', 'fashion-clip')

try:
    modelo = CLIPModel.from_pretrained(MODELO_PATH, local_files_only=True).to(device)
    processador = CLIPProcessor.from_pretrained(MODELO_PATH, local_files_only=True)
except:
    print("Baixando o modelo Fashion-CLIP pela primeira vez...")
    modelo = CLIPModel.from_pretrained("patrickjohncyh/fashion-clip").to(device)
    processador = CLIPProcessor.from_pretrained("patrickjohncyh/fashion-clip")
    os.makedirs(MODELO_PATH, exist_ok=True)
    modelo.save_pretrained(MODELO_PATH)
    processador.save_pretrained(MODELO_PATH)

# --- DECORADOR DE SEGURANÇA ---
def login_obrigatorio(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario_id' not in session:
            flash('Por favor, faça login para acessar esta página.', 'erro')
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function

# --- FUNÇÃO AUXILIAR DE E-MAIL ---
def enviar_email_codigo(destinatario, codigo):
    remetente = "vestia.noreply@gmail.com" 
    senha_app = "mrwk iwsf hlag ogus"

    assunto = "Seu código de verificação - Vest.IA"
    corpo = f"Olá! Seu código de verificação é: {codigo}\n\nSe você não solicitou este código, ignore este e-mail."

    msg = MIMEText(corpo)
    msg['Subject'] = assunto
    msg['From'] = remetente
    msg['To'] = destinatario

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(remetente, senha_app)
        server.sendmail(remetente, destinatario, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"Erro ao enviar e-mail: {e}")
        return False

# ==========================================
# ROTAS DO SISTEMA
# ==========================================
def configure_routes(app):

    # Configuração da pasta de upload para fotos de perfil
    app.config['UPLOAD_PERFIL'] = os.path.join(BASE_DIR, 'static', 'uploads', 'perfil')

    # --- FUNÇÃO AUXILIAR: CLIMA (OPEN-METEO) ---
    def obter_clima_local():
        """Consulta a API do Open-Meteo. Retorna (clima_detectado, temperatura) ou (None, None) se falhar."""
        try:
            # Usando Open-Meteo (não exige chave de API) - Coordenadas baseadas no seu contexto
            url = "https://api.open-meteo.com/v1/forecast?latitude=-8.33&longitude=-36.42&current=temperature_2m"
            resposta = requests.get(url, timeout=5)
            if resposta.status_code == 200:
                dados = resposta.json()
                temp = dados.get("current", {}).get("temperature_2m")
                if temp is not None:
                    if temp >= 25:
                        return "calor", temp
                    elif temp <= 19:
                        return "frio", temp
                    else:
                        return "meia_estacao", temp
        except Exception as e:
            print(f"Erro na API de Clima: {e}. Usando fallback.")
        return None, None

    # --- PÁGINAS BÁSICAS ---
    @app.route('/', methods=['GET'])
    @app.route('/login', methods=['GET'])
    def login_page():
        if 'usuario_id' in session:
            return redirect(url_for('dashboard'))
        return render_template('login.html')

    @app.route('/register', methods=['GET'])
    @app.route('/registrar', methods=['GET'])
    def register_page():
        if 'usuario_id' in session:
            return redirect(url_for('dashboard'))
        return render_template('register.html')

    @app.route('/recuperar_senha')
    def recuperar_senha_page():
        return render_template('esquecisenha.html')

    @app.route('/dashboard')
    @login_obrigatorio
    def dashboard():
        usuario_id = session['usuario_id']
        conn = conectar()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) as total FROM roupas WHERE usuario_id = ?", (usuario_id,))
        total_roupas = cursor.fetchone()['total']

        cursor.execute("SELECT * FROM roupas WHERE usuario_id = ? ORDER BY vezes_usada ASC LIMIT 5", (usuario_id,))
        menos_usadas = cursor.fetchall()
        conn.close()

        return render_template('dashboard.html', total_roupas=total_roupas, menos_usadas=menos_usadas)

    @app.route('/cadastrar')
    @login_obrigatorio
    def cadastrar_page():
        return render_template('cadastrar_roupa.html')

    @app.route('/sugestoes')
    @login_obrigatorio
    def sugestoes_page():
        return render_template('sugestoes.html')

    @app.route('/minhas_roupas')
    @login_obrigatorio
    def roupas_page():
        return render_template('minhas_roupas.html')

    @app.route('/historico_page')
    @login_obrigatorio
    def historico_page():
        return render_template('historico.html')

    # --- APIS DE AUTENTICAÇÃO E CADASTRO ---
    @app.route('/login', methods=['POST'])
    def login():
        dados = request.get_json()
        if not dados:
            return jsonify({"ok": False, "mensagem": "Dados inválidos."}), 400
        
        email = dados.get('email', '').strip()
        senha = dados.get('senha', '').strip()

        usuario = verificar_usuario(email, senha)
        if usuario:
            session['usuario_id'] = usuario['id']
            session['usuario_nome'] = usuario['nome']
            return jsonify({"ok": True, "redirect": url_for('dashboard')})
        else:
            return jsonify({"ok": False, "mensagem": "E-mail ou senha incorretos."})

    @app.route('/registrar', methods=['POST'])
    def registrar():
        dados = request.get_json()
        nome = dados.get('nome')
        email = dados.get('email')
        senha = dados.get('senha')

        if not nome or not email or not senha:
            return jsonify({"ok": False, "mensagem": "Preencha todos os campos!"}), 400

        if email_existe(email):
            return jsonify({"ok": False, "mensagem": "Este e-mail já está cadastrado. Faça login."})

        codigo = str(random.randint(100000, 999999))
        session['temp_nome'] = nome
        session['temp_email'] = email
        session['temp_senha'] = senha
        session['temp_codigo'] = codigo

        enviou = enviar_email_codigo(email, codigo)
        if enviou:
            return jsonify({"ok": True, "mensagem": "Código enviado!"})
        else:
            return jsonify({"ok": False, "mensagem": "Erro ao enviar e-mail."}), 500

    @app.route('/validar_cadastro', methods=['POST'])
    def validar_cadastro():
        try:
            dados = request.get_json()
            codigo_digitado = str(dados.get('codigo', '')).strip()
            codigo_salvo = str(session.get('temp_codigo', '')).strip()

            if codigo_digitado == codigo_salvo:
                nome = session.get('temp_nome')
                email = session.get('temp_email')
                senha = session.get('temp_senha')

                sucesso = cadastrar_usuario(nome, email, senha)
                if sucesso:
                    conn = conectar()
                    c = conn.cursor()
                    c.execute("SELECT id FROM usuarios WHERE email = ?", (email,))
                    user = c.fetchone()
                    conn.close()
                    
                    if user:
                        session['usuario_id'] = user['id']
                        session['usuario_nome'] = nome
                        return jsonify({"ok": True})
                    else:
                        return jsonify({"ok": False, "mensagem": "Erro interno ao logar após criar conta."})
                else:
                    return jsonify({"ok": False, "mensagem": "Esse e-mail já está em uso."})
            else:
                return jsonify({"ok": False, "mensagem": "Código inválido."})
        except Exception as e:
            return jsonify({"ok": False, "mensagem": f"Erro do servidor: {str(e)}"})

    @app.route('/logout')
    def logout():
        session.clear()
        flash('Você saiu da sua conta com sucesso.', 'sucesso') 
        return redirect(url_for('login_page'))

    # --- APIS DE REDEFINIÇÃO DE SENHA ---
    @app.route('/enviar_codigo', methods=['POST'])
    def enviar_codigo_rota():
        dados = request.get_json()
        email = dados.get('email', '').strip()
        
        conn = conectar()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM usuarios WHERE email = ?", (email,))
        usuario = cursor.fetchone()
        conn.close()
        
        if not usuario:
            return jsonify({"ok": False, "mensagem": "Este e-mail não está cadastrado."})
            
        codigo = str(random.randint(100000, 999999))
        session['reset_codigo'] = codigo
        session['reset_email'] = email
        
        sucesso = enviar_email_codigo(email, codigo)
        if sucesso:
            return jsonify({"ok": True})
        else:
            return jsonify({"ok": False, "mensagem": "Erro ao enviar o e-mail. Tente novamente."})

    @app.route('/validar_codigo', methods=['POST'])
    def validar_codigo_esqueci():
        dados = request.get_json()
        codigo_digitado = str(dados.get('codigo', '')).strip()
        codigo_salvo = str(session.get('reset_codigo', '')).strip()
        
        if not codigo_salvo or codigo_salvo == 'None':
            return jsonify({"ok": False, "mensagem": "Sessão expirada. Volte e recomece o processo."})
            
        if codigo_digitado == codigo_salvo:
            return jsonify({"ok": True})
        else:
            return jsonify({"ok": False, "mensagem": "Código inválido! Tente novamente."})

    @app.route('/redefinir_senha', methods=['POST'])
    def redefinir_senha():
        dados = request.get_json()
        nova_senha = dados.get('senha', '').strip()
        email = session.get('reset_email')
        
        if not email:
            return jsonify({"ok": False, "mensagem": "Sessão expirada. Volte ao início."})

        senha_criptografada = generate_password_hash(nova_senha)
            
        conn = conectar()
        cursor = conn.cursor()
        cursor.execute("UPDATE usuarios SET senha = ? WHERE email = ?", (senha_criptografada, email))
        conn.commit()
        conn.close()
        
        session.pop('reset_codigo', None)
        session.pop('reset_email', None)
        return jsonify({"ok": True})

    # --- APIS DO GUARDA-ROUPA E IA ---
    @app.route('/cadastrar_via_imagem', methods=['POST'])
    @login_obrigatorio
    def cadastrar_via_imagem():
        files = request.files.getlist('imagem')
        
        candidatos_tipo = {
            "Camisa": "uma camisa social de botão de manga longa ou curta",
            "Camiseta": "uma camiseta casual basica de algodão manga curta t-shirt",
            "Camisa de Time ou Seleção": "uma camisa esportiva de futebol, camisa de time, camisa de seleção nacional, uniforme esportivo oficial, jersey de clube, camisa da seleção brasileira, camisa de jogador com escudo ou patrocinador",
            "Blusa": "uma blusa feminina ou blusa delicada de frio ou calor",
            "Casaco": "um casaco grosso, jaqueta, moletom, blazer ou casaco de frio",
            "Calça": "uma calça comprida jeans, sarja, moletom ou calça social",
            "Bermuda": "uma bermuda ou short curto casual",
            "Saia": "uma saia feminina curta, média ou longa",
            "Vestido": "um vestido feminino de peça única",
            "Acessório": "qualquer item usado para complementar o visual, como boné, chapéu, cachecol, lenço, cinto, meia, relógio, óculos, brinco, colar, pulseira, bolsa, luva ou cachecol, não serve para cobrir o corpo principal",
            "Calçado": "um calçado, sapato, tênis, bota ou sandália nos pés"
        }

        candidatos_cor = {
            "Preto": "uma peça de roupa totalmente preta escura lisa",
            "Branco": "uma peça de roupa totalmente branca clara lisa",
            "Cinza": "uma peça de roupa cinza ou de cor grafite",
            "Azul": "uma peça de roupa azul clara ou escura",
            "Vermelho": "uma peça de roupa vermelha viva ou vinho",
            "Verde": "uma peça de roupa verde oliva, musgo ou claro",
            "Amarelo": "uma peça de roupa amarela brilhante",
            "Rosa": "uma peça de roupa rosa ou fúcsia",
            "Marrom": "uma peça de roupa marrom ou cor de terra",
            "Bege": "uma peça de roupa beige, creme ou caqui claro",
            "Listrado": "uma peça de roupa com duas cores e com listras verticais, horizontais ou diagonais",
            "Xadrez": "uma peça que é formada somente de quadrados por toda a roupa",
            "Colorido": "uma peça de roupa colorida, estampada com muitas cores misturadas, multicolorida"
        }

        candidatos_ocasiao = {
            "Casual": "roupa casual do dia a dia, despojada e confortável para ficar em casa ou sair com amigos",
            "Formal": "roupa formal de gala, terno completo, alfaiataria ou vestido sofisticado de casamento",
            "Trabalho": "roupa de trabalho formal-casual, escritório ou ambiente corporativo sério",
            "Festa": "roupa estilosa de festa, balada ou evento noturno comemorativo",
            "Esporte": "roupa esportiva de academia, treino, corrida, tactel ou dry-fit"
        }

        candidatos_clima = {
            "Calor": "uma roupa fresca de verão, sem mangas, curta, ideal para dias de sol forte e calor",
            "Frio": "uma roupa pesada de inverno, grossa, de lã ou couro, feita para proteger de frio intenso",
            "Meia-estação": "uma roupa leve de outono ou primavera, de meia manga, nem muito quente nem muito fresca, perfeita para clima ameno ou meia-estação"
        }

        votos_tipo = []
        votos_cor = []
        votos_ocasiao = []
        votos_clima = []
        fotos_base64 = []

        for file in files:
            img_bytes = file.read()
            
            fb64 = base64.b64encode(img_bytes).decode('utf-8')
            fotos_base64.append(f"data:{file.content_type};base64,{fb64}")

            image = Image.open(io.BytesIO(img_bytes)).convert("RGB")

            def classificar_com_precisao(dicionario_candidatos):
                termos_reais = list(dicionario_candidatos.keys())
                frases_contexto = list(dicionario_candidatos.values())
                
                inputs = processador(text=frases_contexto, images=image, return_tensors="pt", padding=True).to(device)
                with torch.no_grad():
                    outputs = modelo(**inputs)
                
                logits_per_image = outputs.logits_per_image
                probs = logits_per_image.softmax(dim=-1)
                idx = probs.argmax().item()
                
                return termos_reais[idx]

            votos_tipo.append(classificar_com_precisao(candidatos_tipo))
            votos_cor.append(classificar_com_precisao(candidatos_cor))
            votos_ocasiao.append(classificar_com_precisao(candidatos_ocasiao))
            votos_clima.append(classificar_com_precisao(candidatos_clima))

        res_tipo = Counter(votos_tipo).most_common(1)[0][0]
        res_cor = Counter(votos_cor).most_common(1)[0][0]
        res_ocasiao = Counter(votos_ocasiao).most_common(1)[0][0]
        res_clima = Counter(votos_clima).most_common(1)[0][0]

        if res_cor in ["Listrado", "Colorido"]:
            nome_sugerido = f"{res_tipo} {res_cor.lower()}"
        else:
            nome_sugerido = f"{res_tipo} {res_cor}"

        return jsonify({
            "dados": {
                "nome": nome_sugerido,
                "tipo": res_tipo,
                "cor": res_cor,
                "ocasiao": res_ocasiao,
                "clima": res_clima
            },
            "fotos_base64": fotos_base64
        })

    @app.route('/salvar_final', methods=['POST'])
    @login_obrigatorio
    def salvar_final():
        usuario_id = session.get('usuario_id')
        if not usuario_id:
            return jsonify({"ok": False, "mensagem": "Sessão expirada. Faça login novamente."}), 401

        dados = request.get_json()
        nome = dados.get('nome')
        tipo = dados.get('tipo', 'Outros').strip()
        cor = dados.get('cor')
        ocasiao = dados.get('ocasiao')
        clima = dados.get('clima')
        fotos_base64 = dados.get('fotos_base64', [])

        pasta_tipo = "".join(c for c in tipo if c.isalnum() or c in (' ', '_', '-')).strip()
        diretorio_tipo = os.path.join(BASE_DIR, 'static', 'uploads', pasta_tipo)
        
        if not os.path.exists(diretorio_tipo):
            os.makedirs(diretorio_tipo)

        caminhos_salvos = []
        for fb64 in fotos_base64:
            if ',' in fb64:
                fb64 = fb64.split(',')[1]
            
            conteudo_foto = base64.b64decode(fb64)
            img = Image.open(io.BytesIO(conteudo_foto))
            nome_arquivo = f"{uuid.uuid4().hex}.jpg"
            caminho_completo = os.path.join(diretorio_tipo, nome_arquivo)
            
            img.convert('RGB').save(caminho_completo, 'JPEG')
            
            caminhos_salvos.append(f"/static/uploads/{pasta_tipo}/{nome_arquivo}")

        cadastrar_roupa(usuario_id, nome, tipo, cor, ocasiao, clima, caminhos_salvos)
        return jsonify({"ok": True, "mensagem": "Roupa guardada com sucesso!"})

    @app.route('/listar', methods=['GET'])
    @login_obrigatorio
    def listar_roupas():
        usuario_id = session.get('usuario_id')
        if not usuario_id:
            return jsonify([])

        conn = conectar()
        conn.row_factory = sqlite3.Row 
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM roupas WHERE usuario_id = ?", (usuario_id,))
        roupas_db = cursor.fetchall()

        lista_final = []
        for r in roupas_db:
            roupa_dict = dict(r)
            cursor.execute("SELECT caminho FROM fotos_roupas WHERE roupa_id = ?", (r['id'],))
            fotos = cursor.fetchall()
            
            roupa_dict['fotos'] = [f['caminho'] for f in fotos]
            lista_final.append(roupa_dict)

        conn.close()
        return jsonify(lista_final)

    @app.route('/sugerir_combinacoes/<int:roupa_id>')
    @login_obrigatorio
    def sugerir_combinacoes(roupa_id):
        usuario_id = session['usuario_id']
        conn = conectar()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM roupas WHERE id = ? AND usuario_id = ?", (roupa_id, usuario_id))
        roupa_base = cursor.fetchone()
        
        if not roupa_base:
            conn.close()
            return jsonify({"erro": "Peça não encontrada"}), 404
            
        roupa_base = dict(roupa_base)
        tipo_base = roupa_base['tipo']
        ocasiao_base = roupa_base['ocasiao']
        clima_base = roupa_base['clima']
        
        superiores = ["Camisa", "Camiseta", "Blusa", "Casaco"]
        inferiores = ["Calça", "Bermuda", "Saia"]
        
        tipos_compativeis = []
        if tipo_base in superiores:
            tipos_compativeis = inferiores + ["Calçado"]
        elif tipo_base in inferiores:
            tipos_compativeis = superiores + ["Calçado"]
        elif tipo_base == "Vestido":
            tipos_compativeis = ["Calçado", "Casaco"]
        elif tipo_base == "Calçado":
            tipos_compativeis = superiores + inferiores + ["Vestido"]
            
        cursor.execute("SELECT * FROM roupas WHERE usuario_id = ? AND id != ?", (usuario_id, roupa_id))
        todas_roupas = [dict(row) for row in cursor.fetchall()]
        
        sugestoes = []
        for r in todas_roupas:
            if r['tipo'] in tipos_compativeis and r['ocasiao'] == ocasiao_base and r['clima'] == clima_base:
                cursor.execute("SELECT caminho FROM fotos_roupas WHERE roupa_id = ? LIMIT 1", (r['id'],))
                foto_row = cursor.fetchone()
                r['foto'] = foto_row['caminho'] if foto_row else None
                sugestoes.append(r)
                
        conn.close()
        return jsonify({
            "peca_selecionada": roupa_base,
            "combinacoes_sugeridas": sugestoes
        })

    # --- API: SUGESTÕES DIÁRIAS (CLIMA) ---
    @app.route('/api/sugestoes_combinacoes')
    @login_obrigatorio
    def api_sugestoes_combinacoes():
        usuario_id = session['usuario_id']
        conn = conectar()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT r.id, r.nome, r.tipo, r.cor, r.clima_ideal, r.ocasiao, f.caminho as foto
            FROM roupas r
            LEFT JOIN (
                SELECT roupa_id, MIN(caminho) as caminho FROM fotos_roupas GROUP BY roupa_id
            ) f ON r.id = f.roupa_id
            WHERE r.usuario_id = ?
        """, (usuario_id,))
        
        roupas = [dict(row) for row in cursor.fetchall()]
        conn.close()

        def gerar_look(clima_alvo):
            pecas_clima = [r for r in roupas if r['clima_ideal'] and clima_alvo.lower() in r['clima_ideal'].lower()]
            if not pecas_clima:
                pecas_clima = roupas # Fallback se não tiver roupas com a tag do clima

            superiores = [p for p in pecas_clima if p['tipo'] and p['tipo'].lower() in ['camisa', 'camiseta', 'blusa', 'casaco', 'jaqueta', 'top', 'moletom']]
            inferiores = [p for p in pecas_clima if p['tipo'] and p['tipo'].lower() in ['calça', 'bermuda', 'short', 'saia', 'jeans']]
            calcados = [p for p in pecas_clima if p['tipo'] and p['tipo'].lower() in ['calçado', 'tenis', 'sapato']]
            
            look = []
            if superiores:
                look.append(random.choice(superiores))
            if inferiores:
                look.append(random.choice(inferiores))
            if calcados:
                look.append(random.choice(calcados))
            
            if not look and pecas_clima:
                look = random.sample(pecas_clima, min(2, len(pecas_clima)))
            return look

        clima_atual, temperatura = obter_clima_local()

        resposta_dados = {
            "clima_atual": clima_atual,
            "temperatura": temperatura,
            "fallback_ativo": clima_atual is None,
            "looks": {
                "calor": gerar_look("Calor"),
                "frio": gerar_look("Frio"),
                "meia_estacao": gerar_look("Meia")
            }
        }
        return jsonify(resposta_dados)

    @app.route('/usar/<int:id>')
    @login_obrigatorio
    def usar(id):
        usuario_id = session.get('usuario_id')
        if not usuario_id:
            return jsonify({"ok": False}), 401

        conn = conectar()
        cursor = conn.cursor()
        
        cursor.execute("SELECT id FROM roupas WHERE id = ? AND usuario_id = ?", (id, usuario_id))
        if cursor.fetchone():
            data_atual = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute("INSERT INTO historico (roupa_id, data_uso) VALUES (?, ?)", (id, data_atual))
            cursor.execute("UPDATE roupas SET vezes_usada = vezes_usada + 1 WHERE id = ?", (id,))
            conn.commit()
            conn.close()
            return jsonify({"ok": True})
        
        conn.close()
        return jsonify({"ok": False, "mensagem": "Operação não permitida."}), 403

    @app.route('/excluir/<int:id>')
    @login_obrigatorio
    def excluir(id):
        usuario_id = session.get('usuario_id')
        if not usuario_id:
            return jsonify({"ok": False, "mensagem": "Não autorizado."}), 401

        nome_excluido = excluir_roupa(id, usuario_id)
        if nome_excluido:
            return jsonify({"ok": True, "mensagem": f"Roupa '{nome_excluido}' excluída."})
        return jsonify({"ok": False, "mensagem": "Erro ou permissão negada."}), 403

    @app.route('/editar/<int:id>', methods=['POST'])
    @login_obrigatorio
    def editar(id):
        usuario_id = session.get('usuario_id')
        if not usuario_id:
            return jsonify({"ok": False, "mensagem": "Não autorizado."}), 401

        dados = request.get_json()
        nome = dados.get('nome')
        tipo = dados.get('tipo')
        cor = dados.get('cor')
        ocasiao = dados.get('ocasiao')
        clima = dados.get('clima')

        try:
            editar_roupa(id, usuario_id, nome, tipo, cor, ocasiao, clima)
            return jsonify({"ok": True, "mensagem": "Roupa atualizada com sucesso!"})
        except Exception as e:
            return jsonify({"ok": False, "mensagem": f"Erro ao editar: {str(e)}"}), 500

    @app.route('/historico')
    @login_obrigatorio
    def historico():
        usuario_id = session.get('usuario_id')
        if not usuario_id:
            return jsonify([]), 401 
        dados = buscar_historico_usuario(usuario_id)
        return jsonify(dados)

    # --- APIS DO PERFIL DO USUÁRIO ---
    @app.route('/perfil')
    @login_obrigatorio
    def perfil():
        usuario_id = session['usuario_id']
        conn = conectar()
        cursor = conn.cursor()
        cursor.execute("SELECT nome, email, foto_url FROM usuarios WHERE id = ?", (usuario_id,))
        user_data = cursor.fetchone()
        conn.close()

        if user_data:
            foto = user_data[2] if user_data[2] else "https://www.gravatar.com/avatar/00000000000000000000000000000000?d=mp&f=y"
            usuario = {
                "nome": user_data[0],
                "email": user_data[1],
                "foto_url": foto
            }
            return render_template('perfil.html', usuario=usuario)
        
        return redirect(url_for('login_page'))

    @app.route('/perfil/atualizar_dados', methods=['POST'])
    @login_obrigatorio
    def atualizar_dados():
        usuario_id = session['usuario_id']
        nome = request.form.get('nome')
        email = request.form.get('email')
        
        conn = conectar()
        cursor = conn.cursor()
        cursor.execute("UPDATE usuarios SET nome = ?, email = ? WHERE id = ?", (nome, email, usuario_id))
        conn.commit()
        conn.close()
        
        flash('Dados da conta atualizados com sucesso!', 'success')
        return redirect(url_for('perfil'))

    @app.route('/perfil/alterar_senha', methods=['POST'])
    @login_obrigatorio
    def alterar_senha():
        usuario_id = session['usuario_id']
        senha_atual = request.form.get('senha_atual')
        nova_senha = request.form.get('nova_senha')
        confirmar_senha = request.form.get('confirmar_senha')
        
        if nova_senha != confirmar_senha:
            flash('As novas senhas não coincidem.', 'error')
            return redirect(url_for('perfil'))
            
        conn = conectar()
        cursor = conn.cursor()
        cursor.execute("SELECT senha FROM usuarios WHERE id = ?", (usuario_id,))
        senha_banco = cursor.fetchone()[0]
        
        hash_senha_atual = generate_password_hash(senha_atual)
        
        if senha_banco != hash_senha_atual: 
            conn.close()
            flash('Sua senha atual está incorreta.', 'error')
            return redirect(url_for('perfil'))
            
        hash_nova_senha = generate_password_hash(nova_senha)
        cursor.execute("UPDATE usuarios SET senha = ? WHERE id = ?", (hash_nova_senha, usuario_id))
        conn.commit()
        conn.close()
        
        flash('Sua senha foi alterada com sucesso!', 'success')
        return redirect(url_for('perfil'))

    @app.route('/perfil/atualizar_foto', methods=['POST'])
    @login_obrigatorio
    def atualizar_foto():
        if 'foto_perfil' not in request.files:
            flash('Nenhum arquivo selecionado', 'error')
            return redirect(url_for('perfil'))
       
        return redirect(url_for('perfil'))
