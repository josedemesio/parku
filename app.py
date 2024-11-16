# Park-U - Sistema de controle de estacionamento
# Atividade de "Software Product: Analysis, Specification, Project & Implementation"
# Faculdade Impacta
# Aluno: José Albério Bezerra Demésio

from flask import Flask, request, jsonify, render_template, redirect, url_for
import pymysql
from datetime import datetime

# Cria uma instância do Flask
app = Flask(__name__)

# Função para conectar ao banco de dados MySQL
def get_db_connection():
    try:
        # Conexão ao banco de dados MySQL
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
        # Caso ocorra um erro na conexão
        print(f"Erro ao conectar ao banco de dados: {e}")
        return None

# Rota para a página inicial
@app.route('/')
def index():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        cursor.execute("SELECT valor_hora FROM configuracoes WHERE id = 1")
        valor_hora = cursor.fetchone()
        valor_hora = valor_hora[0] if valor_hora else 0  # Se não existir, define como 0

        cursor.execute("SELECT COUNT(*) AS total_veiculos FROM registros WHERE horario_saida IS NULL")
        total_veiculos = cursor.fetchone()[0]

        cursor.execute("SELECT total_vagas FROM configuracoes WHERE id = 1")
        total_vagas = cursor.fetchone()[0]

        vagas_disponiveis = total_vagas - total_veiculos

    finally:
        cursor.close()
        conn.close()

    return render_template('index.html', valor_hora=valor_hora, vagas_disponiveis=vagas_disponiveis)

# Rota para a página de entrada de veículos
@app.route('/entrada')
def entrada():
    return render_template('entrada.html')

# Rota para a página de saída de veículos
@app.route('/saida')
def saida():
    return render_template('saida.html')

# Rota para tratar a entrada de veículos (POST)
@app.route('/entrada', methods=['POST'])
def entrada_veiculo():
    # Obtém os dados do formulário (placa e modelo do veículo)
    placa = request.form['placa']
    modelo = request.form['modelo']
    hora_entrada = datetime.now()  # Armazena o horário de entrada do veículo

    # Conecta ao banco de dados
    conn = get_db_connection()
    cursor = conn.cursor()

    # Verifica se o veículo já está no estacionamento sem ter saído
    cursor.execute("""SELECT id FROM registros WHERE placa = %s AND horario_saida IS NULL""", (placa,))
    veiculo_existente = cursor.fetchone()

    # Se o veículo já estiver no estacionamento, exibe mensagem de erro
    if veiculo_existente:
        cursor.close()
        conn.close()
        return render_template('popup.html', message='Veículo já está no estacionamento.', success=False)

    # Insere um novo registro de entrada no banco de dados
    cursor.execute("""INSERT INTO registros (placa, modelo, horario_entrada, tempo_permanencia) VALUES (%s, %s, %s, %s)""", (placa, modelo, hora_entrada, None))
    conn.commit()

    # Fecha a conexão com o banco
    cursor.close()
    conn.close()

    # Exibe mensagem de sucesso
    return render_template('popup.html', message='Entrada registrada com sucesso.', success=True)

# Rota para tratar a saída de veículos (POST)
@app.route('/saida', methods=['POST'])
def saida_veiculo():
    placa = request.form['placa']  # Obtém a placa do veículo
    conn = get_db_connection()  # Conecta ao banco de dados
    cursor = conn.cursor()

    # Verifica se o veículo está no estacionamento (entrada sem saída registrada)
    cursor.execute("""SELECT id, horario_entrada FROM registros WHERE placa = %s AND horario_saida IS NULL LIMIT 1""", (placa,))
    entrada = cursor.fetchone()

    # Se o veículo não estiver no estacionamento, exibe mensagem de erro
    if entrada is None:
        cursor.close()
        conn.close()
        return render_template('popup.html', message='O veículo já saiu ou não está no estacionamento.', success=False)

    # Calcula o tempo de permanência e a hora de saída
    hora_saida = datetime.now()
    tempo_permanencia = hora_saida - entrada[1]  # Calcula a diferença entre a entrada e a saída
    horas_estacionadas = tempo_permanencia.total_seconds() // 3600 + 1  # Cobra no mínimo 1 hora

    # Busca o valor da hora nas configurações
    cursor.execute("SELECT valor_hora FROM configuracoes WHERE id = 1")
    valor_hora = float(cursor.fetchone()[0])  # Converte o valor de Decimal para float

    # Calcula o valor total a ser cobrado
    valor_total = horas_estacionadas * valor_hora

    # Atualiza o registro no banco de dados com o horário de saída e o valor total
    cursor.execute("""UPDATE registros SET horario_saida = %s, tempo_permanencia = %s, valor_total = %s WHERE id = %s""", (hora_saida, tempo_permanencia, valor_total, entrada[0]))
    conn.commit()

    # Fecha a conexão com o banco de dados
    cursor.close()
    conn.close()

    # Exibe mensagem de sucesso com o valor a ser cobrado
    return render_template('popup.html', message=f'Saída registrada com sucesso. Valor a ser cobrado: R$ {valor_total:.2f}', success=True)



# Rota para a página de configurações
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

                # Validação básica: verificar se os valores são positivos
                if valor_hora <= 0 or total_vagas < 0:
                    return render_template('configuracoes.html',
                                           valor_hora=valor_hora,
                                           total_vagas=total_vagas,
                                           error="Valores devem ser positivos.")

                # Utilizando parâmetros nomeados para evitar SQL injection
                cursor.execute("UPDATE configuracoes SET valor_hora = %(valor_hora)s, total_vagas = %(total_vagas)s WHERE id = 1",
                               {'valor_hora': valor_hora, 'total_vagas': total_vagas})
                conn.commit()
                return redirect(url_for('config_system'))
            except ValueError:
                return render_template('configuracoes.html',
                                       valor_hora=valor_hora,
                                       total_vagas=total_vagas,
                                       error="Valores inválidos.")

    except Exception as e:
        print(f"Erro ao acessar o banco de dados: {e}")
        return render_template('error.html', message="Ocorreu um erro ao acessar o banco de dados.")
    finally:
        cursor.close()
        conn.close()

    valor_hora_formatado = f"{valor_hora:.2f}"
    return render_template('configuracoes.html', valor_hora=valor_hora_formatado, total_vagas=total_vagas)

# Rota para gerar relatórios
@app.route('/relatorios', methods=['GET', 'POST'])
def relatorios():
    conn = get_db_connection()  # Conecta ao banco de dados
    cursor = conn.cursor(pymysql.cursors.DictCursor)  # Usar DictCursor para retornar os registros como dicionários

    # Paginação
    page = request.args.get('page', 1, type=int)
    per_page = 25
    offset = (page - 1) * per_page

    if request.method == 'POST':
        placa = request.form.get('placa')
        data_entrada = request.form.get('data_entrada')
        data_saida = request.form.get('data_saida')

        query = "SELECT * FROM registros WHERE 1=1"  # Começa com uma condição sempre verdadeira
        params = []

        if placa:
            query += " AND placa = %s"
            params.append(placa)

        if data_entrada:
            query += " AND horario_entrada >= %s"
            params.append(data_entrada + " 00:00:00")  # Considera o início do dia

        if data_saida:
            query += " AND horario_saida <= %s"
            params.append(data_saida + " 23:59:59")  # Considera o final do dia

        # Se ambos os filtros de data forem fornecidos, vamos garantir que
        # eles sejam aplicados corretamente.
        if data_entrada and data_saida:
            query += " AND horario_entrada BETWEEN %s AND %s"
            params.append(data_entrada + " 00:00:00")  # Considera o início do dia
            params.append(data_saida + " 23:59:59")  # Considera o final do dia

        query += " ORDER BY horario_entrada DESC LIMIT %s OFFSET %s"
        params.append(per_page)
        params.append(offset)

        cursor.execute(query, params)
    else:
        # Busca os últimos 25 registros quando não há filtros
        cursor.execute("SELECT * FROM registros ORDER BY horario_entrada DESC LIMIT %s OFFSET %s", (per_page, offset))

    registros = cursor.fetchall()  # Busca todos os registros

    # Conta o total de registros
    cursor.execute("SELECT COUNT(*) AS total FROM registros")
    total_records_result = cursor.fetchone()

    total_records = total_records_result['total'] if total_records_result else 0

    # Calcula o total de páginas
    total_pages = (total_records + per_page - 1) // per_page  # Cálculo para arredondar para cima

    # Fecha a conexão com o banco
    cursor.close()
    conn.close()

    return render_template('relatorios.html', registros=registros, page=page, total_pages=total_pages)


# Executa o servidor
if __name__ == '__main__':
    app.run(debug=True)
