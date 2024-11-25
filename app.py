from flask import Flask, request, jsonify, render_template, redirect, url_for
import pymysql
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

# Cria uma instância do Flask
app = Flask(__name__)

# Função para conectar ao banco de dados MySQL
def get_db_connection():
    try:
        conn = pymysql.connect(
            host='localhost',
            user='parku',
            password='parku',
            database='parku',
            port=3306
        )
        print("Conexão com o banco de dados bem-sucedida.")
        return conn
    except Exception as e:
        print(f"Erro ao conectar ao banco de dados: {e}")
        return None

# Rota para a página inicial
@app.route('/')
def index():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        # Busca o valor da hora
        cursor.execute("SELECT valor_hora FROM configuracoes WHERE id = 1")
        valor_hora = cursor.fetchone()
        valor_hora = valor_hora[0] if valor_hora else 0

        # Conta os veículos atualmente no estacionamento que não são de mensalistas
        cursor.execute("""
            SELECT COUNT(*) AS total_veiculos_nao_mensalistas
            FROM registros
            WHERE horario_saida IS NULL
            AND placa NOT IN (SELECT placa FROM mensalistas WHERE status = 'Ativo')
        """)
        total_veiculos_nao_mensalistas = cursor.fetchone()[0]

        # Busca o total de vagas do estacionamento
        cursor.execute("SELECT total_vagas FROM configuracoes WHERE id = 1")
        total_vagas = cursor.fetchone()[0]

        # Conta o número de mensalistas com status 'Ativo'
        cursor.execute("SELECT COUNT(*) AS total_mensalistas_ativos FROM mensalistas WHERE status = 'Ativo'")
        total_mensalistas_ativos = cursor.fetchone()[0]

        # Calcula as vagas disponíveis
        vagas_disponiveis = max(0, total_vagas - total_veiculos_nao_mensalistas - total_mensalistas_ativos)

    finally:
        cursor.close()
        conn.close()

    return render_template('index.html', valor_hora=valor_hora, vagas_disponiveis=vagas_disponiveis)

# Rota para a página de entrada de veículos

@app.route('/entrada', methods=['GET', 'POST'])
def entrada_veiculo():
    if request.method == 'POST':
        placa = request.form['placa']
        modelo = request.form['modelo']
        hora_entrada = datetime.now()

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            # Verifica se o veículo já está no estacionamento
            cursor.execute("SELECT id FROM registros WHERE placa = %s AND horario_saida IS NULL", (placa,))
            veiculo_existente = cursor.fetchone()

            if veiculo_existente:
                return render_template('popup.html', message='Veículo já está no estacionamento.', success=False)

            # Verifica se o veículo é de um mensalista ativo
            cursor.execute("SELECT id FROM mensalistas WHERE placa = %s AND status = 'Ativo'", (placa,))
            mensalista = cursor.fetchone()
            is_mensalista = mensalista is not None

            # Registra a entrada do veículo
            cursor.execute("""
                INSERT INTO registros (placa, modelo, horario_entrada, tempo_permanencia)
                VALUES (%s, %s, %s, %s)
            """, (placa, modelo, hora_entrada, None))
            conn.commit()

            if not is_mensalista:
                # Veículo comum, subtraí uma vaga
                cursor.execute("UPDATE configuracoes SET total_vagas = total_vagas - 1 WHERE id = 1")
                conn.commit()

            return render_template('popup.html', message='Entrada registrada com sucesso.', success=True)
        except Exception as e:
            conn.rollback()
            return render_template('popup.html', message=f"Erro ao registrar entrada: {e}", success=False)
        finally:
            cursor.close()
            conn.close()
    return render_template('entrada.html')

# Rota para tratar a saída de veículos
@app.route('/saida', methods=['GET', 'POST'])
def saida_veiculo():
    if request.method == 'POST':
        placa = request.form['placa']
        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            # Verifica se o veículo está no estacionamento
            cursor.execute("SELECT id, horario_entrada FROM registros WHERE placa = %s AND horario_saida IS NULL LIMIT 1", (placa,))
            entrada = cursor.fetchone()

            if entrada is None:
                return render_template('popup.html', message='O veículo já saiu ou não está no estacionamento.', success=False)

            # Verifica se o veículo é de um mensalista
            cursor.execute("SELECT id FROM mensalistas WHERE placa = %s AND status = 'Ativo'", (placa,))
            mensalista = cursor.fetchone()
            is_mensalista = mensalista is not None

            if is_mensalista:
                # Mensalista não paga saída
                cursor.execute("""
                    UPDATE registros SET horario_saida = %s
                    WHERE id = %s
                """, (datetime.now(), entrada[0]))
                conn.commit()
                return render_template('popup.html', message='Saída registrada. Veículo de mensalista.', success=True)

            # Veículo comum, calcula o valor a ser pago
            hora_saida = datetime.now()
            tempo_permanencia = hora_saida - entrada[1]
            horas_estacionadas = tempo_permanencia.total_seconds() // 3600 + 1

            cursor.execute("SELECT valor_hora FROM configuracoes WHERE id = 1")
            valor_hora = float(cursor.fetchone()[0])

            valor_total = horas_estacionadas * valor_hora

            cursor.execute("""
                UPDATE registros SET horario_saida = %s, tempo_permanencia = %s, valor_total = %s
                WHERE id = %s
            """, (hora_saida, tempo_permanencia, valor_total, entrada[0]))
            conn.commit()

            # Adiciona uma vaga disponível
            cursor.execute("UPDATE configuracoes SET total_vagas = total_vagas + 1 WHERE id = 1")
            conn.commit()

            return render_template('popup.html', message=f'Saída registrada com sucesso. Valor a ser cobrado: R$ {valor_total:.2f}', success=True)
        except Exception as e:
            conn.rollback()
            return render_template('popup.html', message=f"Erro ao registrar saída: {e}", success=False)
        finally:
            cursor.close()
            conn.close()
    return render_template('saida.html')

# Rota para configurações
@app.route('/configuracoes', methods=['GET', 'POST'])
def config_system():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        cursor.execute("SELECT valor_hora, total_vagas FROM configuracoes WHERE id = 1")
        config = cursor.fetchone()

        if config:
            valor_hora, total_vagas = config
        else:
            valor_hora = 0
            total_vagas = 0

        if request.method == 'POST':
            try:
                valor_hora = float(request.form['valor_hora'])
                total_vagas = int(request.form['total_vagas'])

                if valor_hora <= 0 or total_vagas < 0:
                    return render_template('configuracoes.html', valor_hora=valor_hora, total_vagas=total_vagas, error="Valores devem ser positivos.")

                cursor.execute("""
                    UPDATE configuracoes SET valor_hora = %s, total_vagas = %s WHERE id = 1
                """, (valor_hora, total_vagas))
                conn.commit()
                return redirect(url_for('config_system'))
            except ValueError:
                return render_template('configuracoes.html', valor_hora=valor_hora, total_vagas=total_vagas, error="Valores inválidos.")
    finally:
        cursor.close()
        conn.close()

    return render_template('configuracoes.html', valor_hora=f"{valor_hora:.2f}", total_vagas=total_vagas)

# Rota para relatórios
@app.route('/relatorios', methods=['GET', 'POST'])
def relatorios():
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    page = request.args.get('page', 1, type=int)
    per_page = 25
    offset = (page - 1) * per_page

    if request.method == 'POST':
        placa = request.form.get('placa')
        data_entrada = request.form.get('data_entrada')
        data_saida = request.form.get('data_saida')

        query = "SELECT * FROM registros WHERE 1=1"
        params = []

        if placa:
            query += " AND placa = %s"
            params.append(placa)
        if data_entrada:
            query += " AND horario_entrada >= %s"
            params.append(data_entrada + " 00:00:00")
        if data_saida:
            query += " AND horario_saida <= %s"
            params.append(data_saida + " 23:59:59")

        query += " ORDER BY horario_entrada DESC LIMIT %s OFFSET %s"
        params.extend([per_page, offset])

        cursor.execute(query, params)
    else:
        cursor.execute("SELECT * FROM registros ORDER BY horario_entrada DESC LIMIT %s OFFSET %s", (per_page, offset))

    registros = cursor.fetchall()
    cursor.execute("SELECT COUNT(*) AS total FROM registros")
    total_records = cursor.fetchone()['total']

    total_pages = (total_records + per_page - 1) // per_page

    cursor.close()
    conn.close()

    return render_template('relatorios.html', registros=registros, page=page, total_pages=total_pages)

@app.route('/mensalistas', methods=['GET'])
def listar_mensalistas():
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    try:
        cursor.execute("SELECT * FROM mensalistas ORDER BY id DESC")
        mensalistas = cursor.fetchall()

    finally:
        cursor.close()
        conn.close()

    return render_template('mensalistas.html', mensalistas=mensalistas)

# Rota para gerenciar mensalistas
@app.route('/mensalistas/cadastrar', methods=['GET', 'POST'])
def cadastrar_mensalista():
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        if request.method == 'POST':
            nome = request.form['nome']
            placa = request.form['placa']
            modelo = request.form['modelo']
            telefone = request.form['telefone']
            email = request.form['email']
            data_inicio = datetime.strptime(request.form['data_inicio'], '%Y-%m-%d').date()  # Data inicial
            valor_mensal = float(request.form.get('valor_mensal', '0').replace('R$', '').replace(',', '.'))

            # Insere o mensalista
            cursor.execute("""
                INSERT INTO mensalistas (nome, placa, modelo, telefone, email, data_inicio, valor_mensal)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (nome, placa, modelo, telefone, email, data_inicio, valor_mensal))
            mensalista_id = cursor.lastrowid

            # Gerar mensalidades desde a data de início até hoje
            data_vencimento = data_inicio
            hoje = datetime.now().date()

            while data_vencimento <= hoje:
                # Inserir mensalidade no banco
                cursor.execute("""
                    INSERT INTO pagamentos_mensalistas (mensalista_id, valor_pago, data_pagamento, data_vencimento)
                    VALUES (%s, %s, %s, %s)
                """, (mensalista_id, valor_mensal if data_vencimento == data_inicio else 0.00,
                      datetime.now() if data_vencimento == data_inicio else None, data_vencimento))

                # Incrementa para o próximo mês usando relativedelta
                data_vencimento += relativedelta(months=+1)

            conn.commit()

            return render_template('popup.html', message='Mensalista cadastrado com sucesso!', success=True)

    except Exception as e:
        return render_template('popup.html', message=f"Erro ao cadastrar mensalista: {e}", success=False)

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    return render_template('cadastrar.html')

# Rota para gerenciar pagamentos de mensalistas
@app.route('/pagamentos', methods=['GET', 'POST'])
def pagamentos():
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    pagamentos = []
    total_recebido = 0

    try:
        # Busca os filtros do formulário
        mensalista_id = request.form.get('mensalista_id')
        data_inicio = request.form.get('data_inicio')
        data_fim = request.form.get('data_fim')

        # Base da query
        query = """
            SELECT pagamentos_mensalistas.id, pagamentos_mensalistas.data_pagamento, pagamentos_mensalistas.valor_pago,
                   pagamentos_mensalistas.data_vencimento, mensalistas.nome, mensalistas.placa,
                   CASE 
                       WHEN pagamentos_mensalistas.data_pagamento IS NULL AND pagamentos_mensalistas.data_vencimento < NOW() THEN 'Pendente'
                       ELSE 'Quitado'
                   END AS status
            FROM pagamentos_mensalistas
            INNER JOIN mensalistas ON pagamentos_mensalistas.mensalista_id = mensalistas.id
            WHERE 1=1
        """
        params = []

        # Adiciona filtros dinamicamente
        if mensalista_id:
            query += " AND pagamentos_mensalistas.mensalista_id = %s"
            params.append(mensalista_id)
        if data_inicio:
            query += " AND pagamentos_mensalistas.data_vencimento >= %s"
            params.append(data_inicio)
        if data_fim:
            query += " AND pagamentos_mensalistas.data_vencimento <= %s"
            params.append(data_fim)

        query += " ORDER BY pagamentos_mensalistas.data_vencimento ASC"

        # Executa a query
        cursor.execute(query, params)
        pagamentos = cursor.fetchall()

        # Calcula o total recebido
        total_recebido = sum(p['valor_pago'] for p in pagamentos if p['status'] == 'Quitado')

        # Busca a lista de mensalistas para o filtro
        cursor.execute("SELECT id, nome FROM mensalistas")
        mensalistas = cursor.fetchall()

    finally:
        cursor.close()
        conn.close()

    # Renderiza o template passando os dados
    return render_template(
        'pagamentos.html',
        pagamentos=pagamentos,
        mensalistas=mensalistas,
        total_recebido=total_recebido
    )

@app.route('/pagamentos/registrar', methods=['POST'])
def registrar_pagamento():
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        pagamento_id = int(request.form['pagamento_id'])  # ID do pagamento
        data_pagamento = datetime.now()

        # Verifique se o pagamento existe
        cursor.execute("""
            SELECT pagamentos_mensalistas.id, pagamentos_mensalistas.mensalista_id, mensalistas.valor_mensal
            FROM pagamentos_mensalistas
            JOIN mensalistas ON pagamentos_mensalistas.mensalista_id = mensalistas.id
            WHERE pagamentos_mensalistas.id = %s
        """, (pagamento_id,))
        pagamento = cursor.fetchone()

        if not pagamento:
            raise ValueError("Pagamento não encontrado.")

        mensalista_id = pagamento[1]
        valor_mensal = pagamento[2]  # Valor da mensalidade do usuário

        # Atualiza o pagamento com o valor da mensalidade
        cursor.execute("""
            UPDATE pagamentos_mensalistas
            SET valor_pago = %s, data_pagamento = %s
            WHERE id = %s
        """, (valor_mensal, data_pagamento, pagamento_id))

        conn.commit()

        return render_template('popup.html', message='Pagamento registrado com sucesso!', success=True)

    except Exception as e:
        return render_template('popup.html', message=f"Erro ao registrar pagamento: {e}", success=False)

    finally:
        cursor.close()
        conn.close()


@app.route('/mensalistas/editar/<int:id>', methods=['GET', 'POST'])
def editar_mensalista(id):
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    try:
        if request.method == 'POST':
            # Dados atualizados enviados pelo formulário
            nome = request.form['nome']
            placa = request.form['placa']
            modelo = request.form['modelo']
            telefone = request.form['telefone']
            email = request.form['email']
            valor_mensal = request.form.get('valor_mensal', 'R$ 0,00').replace('R$', '').replace(',', '.')

            # Atualiza os dados do mensalista no banco
            cursor.execute("""
                UPDATE mensalistas
                SET nome = %s, placa = %s, modelo = %s, telefone = %s, email = %s, valor_mensal = %s
                WHERE id = %s
            """, (nome, placa, modelo, telefone, email, valor_mensal, id))
            conn.commit()

            return render_template('popup.html', message='Dados do mensalista atualizados com sucesso!', success=True)

        # Busca os dados do mensalista para preencher o formulário de edição
        cursor.execute("SELECT * FROM mensalistas WHERE id = %s", (id,))
        mensalista = cursor.fetchone()

        if not mensalista:
            return render_template('popup.html', message='Mensalista não encontrado!', success=False)

    finally:
        cursor.close()
        conn.close()

    return render_template('editar_mensalista.html', mensalista=mensalista)

@app.route('/mensalistas/alterar_status/<int:mensalista_id>', methods=['POST'])
def alterar_status_mensalista(mensalista_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Verifica o status atual do mensalista
        cursor.execute("SELECT status, valor_mensal FROM mensalistas WHERE id = %s", (mensalista_id,))
        mensalista = cursor.fetchone()
        if not mensalista:
            raise ValueError("Mensalista não encontrado.")

        status_atual, valor_mensal = mensalista

        if status_atual == 'Ativo':
            # Cancela o mensalista
            novo_status = 'Cancelado'
        else:
            # Reativa o mensalista
            novo_status = 'Ativo'
            data_pagamento = datetime.now().date()

            # Verifica se já existe um pagamento para o dia atual
            cursor.execute("""
                SELECT COUNT(*) FROM pagamentos_mensalistas
                WHERE mensalista_id = %s AND data_pagamento = %s
            """, (mensalista_id, data_pagamento))
            pagamento_existente = cursor.fetchone()[0]

            if pagamento_existente == 0:
                # Se não existir pagamento para hoje, insere um novo
                data_vencimento = data_pagamento + relativedelta(months=+1)
                cursor.execute("""
                    INSERT INTO pagamentos_mensalistas (mensalista_id, data_pagamento, valor_pago, data_vencimento)
                    VALUES (%s, %s, %s, %s)
                """, (mensalista_id, data_pagamento, valor_mensal, data_vencimento))

        # Atualiza o status do mensalista
        cursor.execute("UPDATE mensalistas SET status = %s WHERE id = %s", (novo_status, mensalista_id))
        conn.commit()

        return render_template('popup.html', message=f"Status alterado para {novo_status} com sucesso!", success=True)

    except Exception as e:
        return render_template('popup.html', message=f"Erro ao alterar status: {e}", success=False)

    finally:
        cursor.close()
        conn.close()


if __name__ == '__main__':
    app.run(debug=True)
