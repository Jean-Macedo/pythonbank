-- Funções de movimentação (DT-02).
--
-- Toda operação que mexe em dinheiro acontece dentro de uma dessas funções, e
-- portanto dentro de uma única transação do PostgreSQL. A aplicação nunca lê o
-- saldo, calcula em Python e regrava: isso seria read-modify-write, e duas
-- operações concorrentes se sobrescreveriam.
--
-- A verificação de saldo é a própria cláusula `where` do `update` (RN-1.10).
-- Um `select` anterior à escrita abriria uma janela entre checar e gravar.
--
-- Os códigos levantados são os de docs/03-contrato-api.md.

-- ---------------------------------------------------------------- depósito --
create or replace function realizar_deposito(p_conta_id bigint, p_valor numeric)
returns numeric language plpgsql as $$
declare v_saldo numeric(15,2);
begin
  if p_valor is null or p_valor <= 0 then
    raise exception 'VALOR_INVALIDO';
  end if;

  update contas set saldo = saldo + p_valor
   where id = p_conta_id and ativa
   returning saldo into v_saldo;

  -- RN-1.13: conta inativa é indistinguível de inexistente para quem chama
  if not found then raise exception 'CONTA_NAO_ENCONTRADA'; end if;

  insert into transacoes (conta_id, tipo, valor, saldo_apos)
  values (p_conta_id, 'deposito', p_valor, v_saldo);

  return v_saldo;
end; $$;

-- ------------------------------------------------------------------ saque --
create or replace function realizar_saque(p_conta_id bigint, p_valor numeric)
returns numeric language plpgsql as $$
declare v_saldo numeric(15,2);
begin
  if p_valor is null or p_valor <= 0 then
    raise exception 'VALOR_INVALIDO';
  end if;

  update contas set saldo = saldo - p_valor
   where id = p_conta_id and ativa and saldo >= p_valor
   returning saldo into v_saldo;

  if not found then
    -- distingue os dois motivos só depois de a escrita ter falhado
    if exists (select 1 from contas where id = p_conta_id and ativa) then
      raise exception 'SALDO_INSUFICIENTE';
    else
      raise exception 'CONTA_NAO_ENCONTRADA';
    end if;
  end if;

  insert into transacoes (conta_id, tipo, valor, saldo_apos)
  values (p_conta_id, 'saque', p_valor, v_saldo);

  return v_saldo;
end; $$;

-- ----------------------------------------------------------- transferência --
create or replace function transferir(
  p_origem bigint, p_destino bigint, p_valor numeric
) returns numeric language plpgsql as $$
declare
  v_saldo_origem  numeric(15,2);
  v_saldo_destino numeric(15,2);
begin
  if p_valor is null or p_valor <= 0 then
    raise exception 'VALOR_INVALIDO';
  end if;
  if p_origem = p_destino then
    raise exception 'CONTAS_IGUAIS';
  end if;

  -- RN-1.11: lock nas duas contas em ordem crescente de id. Sem a ordem fixa,
  -- A→B e B→A simultâneas travam uma na outra e o Postgres aborta uma delas.
  perform id from contas
   where id in (p_origem, p_destino)
   order by id
     for update;

  update contas set saldo = saldo - p_valor
   where id = p_origem and ativa and saldo >= p_valor
   returning saldo into v_saldo_origem;

  if not found then
    if exists (select 1 from contas where id = p_origem and ativa) then
      raise exception 'SALDO_INSUFICIENTE';
    else
      raise exception 'CONTA_NAO_ENCONTRADA';
    end if;
  end if;

  update contas set saldo = saldo + p_valor
   where id = p_destino and ativa
   returning saldo into v_saldo_destino;

  if not found then raise exception 'CONTA_NAO_ENCONTRADA'; end if;

  insert into transacoes (conta_id, tipo, valor, saldo_apos, contraparte_id)
  values (p_origem,  'transferencia_saida',   p_valor, v_saldo_origem,  p_destino),
         (p_destino, 'transferencia_entrada', p_valor, v_saldo_destino, p_origem);

  return v_saldo_origem;
end; $$;

-- ------------------------------------------------------ abertura e encerramento --
create or replace function abrir_conta(
  p_cliente_id bigint, p_tipo text, p_apelido text default null
) returns contas language plpgsql as $$
declare v_conta contas;
begin
  insert into contas (cliente_id, tipo, apelido)
  values (p_cliente_id, p_tipo, nullif(trim(p_apelido), ''))
  returning * into v_conta;
  return v_conta;
exception
  when unique_violation then raise exception 'APELIDO_DUPLICADO';
  when check_violation  then raise exception 'TIPO_DE_CONTA_INVALIDO';
end; $$;

create or replace function encerrar_conta(p_conta_id bigint)
returns void language plpgsql as $$
begin
  -- desativa, nunca apaga: o ledger precisa continuar íntegro
  update contas set ativa = false
   where id = p_conta_id and ativa and saldo = 0;

  if not found then
    if exists (select 1 from contas where id = p_conta_id and ativa) then
      raise exception 'CONTA_NAO_ENCERRAVEL';
    else
      raise exception 'CONTA_NAO_ENCONTRADA';
    end if;
  end if;
end; $$;

-- --------------------------------------------------------- reconciliação ----
-- CA-02: deve retornar zero linhas sempre. É o teste de integridade do sistema.
create or replace view contas_divergentes as
select c.id, c.agencia, c.numero, c.saldo, l.saldo_ledger
  from contas c
  left join lateral (
       select coalesce(sum(
                case when t.tipo in ('deposito','transferencia_entrada')
                     then t.valor else -t.valor end), 0) as saldo_ledger
         from transacoes t
        where t.conta_id = c.id
  ) l on true
 where c.saldo is distinct from l.saldo_ledger;

comment on view contas_divergentes is
  'CA-02: qualquer linha aqui significa que saldo e ledger divergiram.';
