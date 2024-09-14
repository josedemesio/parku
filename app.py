# Park-U - Sistema de controle de estacionamento
# Atividade de "Software Product: Analysis, Specification, Project & Implementation"
# Faculdade Impacta
# Aluno: José Albério Bezerra Demésio

from flask import Flask, request, jsonify, render_template
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
    return render_template('index.html')

# Rota para a página de entrada de veículos
@app.route('/entrada')
def entrada():
    return render_template('entrada.html')

# Rota para a página de saída de veículos
@app.route('/saida')
def saida():
    return render_template('saida.html')

# Rota para a página de configurações
@app.route('/configuracoes')
def configuracoes():
    return render_template('configuracoes.html')

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
    cursor.execute("""
        SELECT id FROM registros WHERE placa = %s AND horario_saida IS NULL
    """, (placa,))
    veiculo_existente = cursor.fetchone()

    # Se o veículo já estiver no estacionamento, exibe mensagem de erro
    if veiculo_existente:
        cursor.close()
        conn.close()
        return render_template('popup.html', message='Veículo já está no estacionamento.', success=False)

    # Insere um novo registro de entrada no banco de dados
    cursor.execute("""
        INSERT INTO registros (placa, modelo, horario_entrada, tempo_permanencia)
        VALUES (%s, %s, %s, %s)
    """, (placa, modelo, hora_entrada, None))
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
    cursor.execute("""
        SELECT id, horario_entrada
        FROM registros
        WHERE placa = %s AND horario_saida IS NULL
        LIMIT 1
    """, (placa,))
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
    cursor.execute("""
        UPDATE registros
        SET horario_saida = %s, tempo_permanencia = %s, valor_total = %s
        WHERE id = %s
    """, (hora_saida, tempo_permanencia, valor_total, entrada[0]))
    conn.commit()

    # Fecha a conexão com o banco de dados
    cursor.close()
    conn.close()

    # Exibe mensagem de sucesso com o valor a ser cobrado
    return render_template('popup.html', message=f'Saída registrada com sucesso. Valor a ser cobrado: R$ {valor_total:.2f}', success=True)

# Rota para exibir e salvar as configurações do sistema
@app.route('/configuracoes', methods=['GET', 'POST'])
def config_system():
    if request.method == 'POST':
        valor_hora = request.form['valor_hora']  # Obtém o valor da hora do formulário
        conn = get_db_connection()  # Conecta ao banco de dados
        cursor = conn.cursor()

        # Atualiza o valor da hora no banco de dados
        cursor.execute("UPDATE configuracoes SET valor_hora = %s WHERE id = 1", (valor_hora,))
        conn.commit()

        # Fecha a conexão com o banco
        cursor.close()
        conn.close()

        # Exibe mensagem de sucesso ao salvar as configurações
        return render_template('popup.html', message='Configurações salvas com sucesso.', success=True)

    # Exibe a página de configurações
    return render_template('configuracoes.html')


# Inicia o servidor Flask, permitindo conexões externas na porta 5000
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
