-- Corrige duas condições de corrida introduzidas na camada da API (Fase 2).
--
-- Ambas eram o mesmo defeito que a DT-02 existe para eliminar — ler, decidir em
-- Python e escrever depois — só que uma camada acima de onde ele foi corrigido
-- na Fase 1.
--
-- 1. O id do lançamento era buscado por uma segunda consulta ("último da
--    conta"), então sob concorrência o cliente recebia o comprovante de outra
--    transação. Medido: 20 depósitos simultâneos devolveram 3 ids distintos
--    para 20 lançamentos reais.
--
-- 2. O limite de contas era verificado com um `select count(*)` anterior ao
--    `insert`. Medido: limite 5, cliente com 4, 10 aberturas simultâneas — todas
--    aceitas, terminando com 14 contas.
--
-- As funções mudam de tipo de retorno, o que exige `drop` antes de recriar:
-- `create or replace` não altera assinatura.

-- ---------------------------------------------------------------- depósito --
drop function if exists realizar_deposito(bigint, numeric);

create function realizar_deposito(
  p_conta_id       bigint,
  p_valor          numeric,
  out saldo        numeric,
  out transacao_id bigint
) language plpgsql as $$
declare
  v_saldo numeric(15,2);
  v_id    bigint;
begin
  if p_valor is null or p_valor <= 0 then
    raise exception 'VALOR_INVALIDO';
  end if;

  update contas c set saldo = c.saldo + p_valor
   where c.id = p_conta_id and c.ativa
   returning c.saldo into v_saldo;
  if not found then raise exception 'CONTA_NAO_ENCONTRADA'; end if;

  -- o id vem do próprio insert: não há como pertencer a outra transação
  insert into transacoes (conta_id, tipo, valor, saldo_apos)
  values (p_conta_id, 'deposito', p_valor, v_saldo)
  returning id into v_id;

  saldo := v_saldo;
  transacao_id := v_id;
end; $$;

-- ------------------------------------------------------------------ saque --
drop function if exists realizar_saque(bigint, numeric);

create function realizar_saque(
  p_conta_id       bigint,
  p_valor          numeric,
  out saldo        numeric,
  out transacao_id bigint
) language plpgsql as $$
declare
  v_saldo numeric(15,2);
  v_id    bigint;
begin
  if p_valor is null or p_valor <= 0 then
    raise exception 'VALOR_INVALIDO';
  end if;

  update contas c set saldo = c.saldo - p_valor
   where c.id = p_conta_id and c.ativa and c.saldo >= p_valor
   returning c.saldo into v_saldo;

  if not found then
    if exists (select 1 from contas where id = p_conta_id and ativa) then
      raise exception 'SALDO_INSUFICIENTE';
    else
      raise exception 'CONTA_NAO_ENCONTRADA';
    end if;
  end if;

  insert into transacoes (conta_id, tipo, valor, saldo_apos)
  values (p_conta_id, 'saque', p_valor, v_saldo)
  returning id into v_id;

  saldo := v_saldo;
  transacao_id := v_id;
end; $$;

-- ----------------------------------------------------------- transferência --
drop function if exists transferir(bigint, bigint, numeric);

create function transferir(
  p_origem         bigint,
  p_destino        bigint,
  p_valor          numeric,
  out saldo        numeric,
  out transacao_id bigint
) language plpgsql as $$
declare
  v_saldo_origem  numeric(15,2);
  v_saldo_destino numeric(15,2);
  v_id            bigint;
begin
  if p_valor is null or p_valor <= 0 then
    raise exception 'VALOR_INVALIDO';
  end if;
  if p_origem = p_destino then
    raise exception 'CONTAS_IGUAIS';
  end if;

  -- ordem crescente de id: A→B e B→A simultâneas não travam uma na outra
  perform id from contas
   where id in (p_origem, p_destino)
   order by id
     for update;

  update contas c set saldo = c.saldo - p_valor
   where c.id = p_origem and c.ativa and c.saldo >= p_valor
   returning c.saldo into v_saldo_origem;

  if not found then
    if exists (select 1 from contas where id = p_origem and ativa) then
      raise exception 'SALDO_INSUFICIENTE';
    else
      raise exception 'CONTA_NAO_ENCONTRADA';
    end if;
  end if;

  update contas c set saldo = c.saldo + p_valor
   where c.id = p_destino and c.ativa
   returning c.saldo into v_saldo_destino;
  if not found then raise exception 'CONTA_NAO_ENCONTRADA'; end if;

  insert into transacoes (conta_id, tipo, valor, saldo_apos, contraparte_id)
  values (p_origem,  'transferencia_saida',   p_valor, v_saldo_origem,  p_destino),
         (p_destino, 'transferencia_entrada', p_valor, v_saldo_destino, p_origem);

  -- o comprovante devolvido é o da perna de saída, que é a do chamador
  select t.id into v_id
    from transacoes t
   where t.conta_id = p_origem and t.tipo = 'transferencia_saida'
   order by t.id desc limit 1;

  saldo := v_saldo_origem;
  transacao_id := v_id;
end; $$;

-- ------------------------------------------------------------ abrir conta --
drop function if exists abrir_conta(bigint, text, text);

create function abrir_conta(
  p_cliente_id     bigint,
  p_tipo           text,
  p_apelido        text default null,
  p_limite_contas  int  default null
) returns contas language plpgsql as $$
declare
  v_conta  contas;
  v_ativas int;
begin
  -- checagem explícita do tipo: antes, qualquer `check_violation` virava
  -- TIPO_DE_CONTA_INVALIDO, inclusive a do apelido em branco
  if p_tipo is null or p_tipo not in ('corrente', 'poupanca') then
    raise exception 'TIPO_DE_CONTA_INVALIDO';
  end if;

  -- Trava a linha do cliente até o fim da função. É isto que serializa as
  -- aberturas do mesmo titular: sem o lock, requisições concorrentes leem a
  -- mesma contagem e todas concluem que ainda há vaga.
  perform 1 from clientes where id = p_cliente_id for update;
  if not found then raise exception 'CLIENTE_NAO_ENCONTRADO'; end if;

  -- O limite continua sendo política da aplicação (DT-05): quem decide o
  -- número é o Python, que o envia. O banco só o aplica sem abrir janela.
  if p_limite_contas is not null then
    select count(*) into v_ativas
      from contas where cliente_id = p_cliente_id and ativa;
    if v_ativas >= p_limite_contas then
      raise exception 'LIMITE_DE_CONTAS';
    end if;
  end if;

  insert into contas (cliente_id, tipo, apelido)
  values (p_cliente_id, p_tipo, nullif(trim(p_apelido), ''))
  returning * into v_conta;

  return v_conta;
exception
  when unique_violation then raise exception 'APELIDO_DUPLICADO';
end; $$;
