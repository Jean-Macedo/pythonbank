-- Estorno.
--
-- O ledger continua append-only: o estorno é um lançamento **novo**, de sinal
-- oposto, ligado ao original por `estorno_de`. O lançamento estornado não é
-- tocado — nem apagado, nem marcado, nem alterado. É por isso que este recurso
-- cabe sem mudar o modelo: a DT-03 sempre disse que correção é lançamento novo,
-- e aqui essa frase vira código.
--
-- Quem pode estornar o quê:
--
--   deposito              → devolve o dinheiro (débito). Exige saldo.
--   saque                 → devolve o dinheiro (crédito).
--   transferencia_saida   → desfaz as duas pernas. Exige saldo no destino.
--   transferencia_entrada → **não**. Quem recebeu não desfaz o que o outro
--                           mandou; para devolver, faz uma transferência nova.
--                           Permitir isso deixaria alguém puxar de volta o
--                           dinheiro de uma conta alheia sem que o dono agisse.

-- --------------------------------------------------------------- colunas ---
alter table transacoes
  add column estorno_de bigint references transacoes(id) on delete restrict;

-- Um lançamento só pode ser estornado uma vez. Sem isto, duas requisições
-- simultâneas estornariam o mesmo lançamento duas vezes e o dinheiro sairia
-- em dobro — a mesma corrida corrigida no limite de contas, agora aqui.
create unique index transacoes_estorno_unico_idx
    on transacoes (estorno_de) where estorno_de is not null;

-- Novos tipos. O sinal continua vindo do tipo, como nos demais.
alter table transacoes drop constraint transacoes_tipo_check;
alter table transacoes add constraint transacoes_tipo_check check (
  tipo in ('deposito', 'saque',
           'transferencia_saida', 'transferencia_entrada',
           'estorno_entrada', 'estorno_saida')
);

-- Contraparte agora também vale para o estorno de transferência, que tem duas
-- pernas como o original.
alter table transacoes drop constraint contraparte_coerente;
alter table transacoes add constraint contraparte_coerente check (
  case
    when tipo in ('transferencia_saida', 'transferencia_entrada')
      then contraparte_id is not null
    when tipo in ('deposito', 'saque')
      then contraparte_id is null
    else true  -- estorno: tem contraparte se o original tinha
  end
);

-- Estorno só existe apontando para um original, e original nenhum é estorno.
alter table transacoes add constraint estorno_coerente check (
  (tipo in ('estorno_entrada', 'estorno_saida')) = (estorno_de is not null)
);

comment on column transacoes.estorno_de is
  'Lançamento que este estorna. O original permanece intacto (DT-03).';

-- --------------------------------------------------------- reconciliação ---
-- `estorno_entrada` soma como entrada; `estorno_saida` subtrai. Sem incluí-los,
-- a view acusaria divergência em toda conta que tivesse um estorno — e o
-- CA-02 passaria a falhar por engano.
create or replace view contas_divergentes as
select c.id, c.agencia, c.numero, c.saldo, l.saldo_ledger
  from contas c
  left join lateral (
       select coalesce(sum(
                case when t.tipo in ('deposito', 'transferencia_entrada',
                                     'estorno_entrada')
                     then t.valor else -t.valor end), 0) as saldo_ledger
         from transacoes t
        where t.conta_id = c.id
  ) l on true
 where c.saldo is distinct from l.saldo_ledger;

-- --------------------------------------------------------------- função ----
create or replace function estornar(
  p_transacao_id   bigint,
  p_conta_id       bigint,
  p_janela_dias    int default null,
  out saldo        numeric,
  out transacao_id bigint
) language plpgsql as $$
declare
  v_original    transacoes;
  v_contraparte transacoes;
  v_saldo       numeric(15,2);
  v_saldo_outro numeric(15,2);
  v_id          bigint;
begin
  -- Trava o original: sem isto, dois pedidos simultâneos passariam os dois
  -- pela verificação de "ainda não estornado" antes de qualquer um escrever.
  select * into v_original from transacoes where id = p_transacao_id for update;
  if not found then raise exception 'LANCAMENTO_NAO_ENCONTRADO'; end if;

  -- A conta vem de quem chamou, já verificada como dele pela API. Confirmar
  -- aqui impede estornar lançamento de outra conta passando o id direto.
  if v_original.conta_id <> p_conta_id then
    raise exception 'LANCAMENTO_NAO_ENCONTRADO';
  end if;

  if v_original.tipo = 'transferencia_entrada' then
    raise exception 'ESTORNO_NAO_PERMITIDO';
  end if;
  if v_original.tipo in ('estorno_entrada', 'estorno_saida') then
    raise exception 'ESTORNO_DE_ESTORNO';
  end if;
  if exists (select 1 from transacoes where estorno_de = p_transacao_id) then
    raise exception 'JA_ESTORNADO';
  end if;

  -- A janela é política da aplicação (DT-05): o número vem do Python, e o
  -- banco só o aplica sem abrir janela entre verificar e escrever.
  if p_janela_dias is not null
     and v_original.data_hora < now() - make_interval(days => p_janela_dias) then
    raise exception 'FORA_DA_JANELA_DE_ESTORNO';
  end if;

  -- ------------------------------------------------------------ depósito --
  if v_original.tipo = 'deposito' then
    update contas c set saldo = c.saldo - v_original.valor
     where c.id = p_conta_id and c.ativa and c.saldo >= v_original.valor
     returning c.saldo into v_saldo;
    if not found then raise exception 'SALDO_INSUFICIENTE'; end if;

    insert into transacoes (conta_id, tipo, valor, saldo_apos, estorno_de)
    values (p_conta_id, 'estorno_saida', v_original.valor, v_saldo, p_transacao_id)
    returning id into v_id;

  -- --------------------------------------------------------------- saque --
  elsif v_original.tipo = 'saque' then
    update contas c set saldo = c.saldo + v_original.valor
     where c.id = p_conta_id and c.ativa
     returning c.saldo into v_saldo;
    if not found then raise exception 'CONTA_NAO_ENCONTRADA'; end if;

    insert into transacoes (conta_id, tipo, valor, saldo_apos, estorno_de)
    values (p_conta_id, 'estorno_entrada', v_original.valor, v_saldo, p_transacao_id)
    returning id into v_id;

  -- ------------------------------------------------------- transferência --
  else
    -- a perna espelho, na conta de destino
    select * into v_contraparte from transacoes
     where conta_id = v_original.contraparte_id
       and tipo = 'transferencia_entrada'
       and contraparte_id = p_conta_id
       and valor = v_original.valor
       and data_hora = v_original.data_hora
     limit 1;
    if not found then raise exception 'LANCAMENTO_NAO_ENCONTRADO'; end if;

    -- mesma ordem de lock da transferência, pelo mesmo motivo
    perform id from contas
     where id in (p_conta_id, v_original.contraparte_id) order by id for update;

    update contas c set saldo = c.saldo - v_original.valor
     where c.id = v_original.contraparte_id and c.ativa
       and c.saldo >= v_original.valor
     returning c.saldo into v_saldo_outro;
    if not found then raise exception 'SALDO_INSUFICIENTE_NO_DESTINO'; end if;

    update contas c set saldo = c.saldo + v_original.valor
     where c.id = p_conta_id and c.ativa
     returning c.saldo into v_saldo;
    if not found then raise exception 'CONTA_NAO_ENCONTRADA'; end if;

    -- Dois inserts separados, não um `values (a), (b) returning into`: aquele
    -- devolve duas linhas para uma variável escalar e estoura. O `returning`
    -- precisa ser o da perna de quem chamou, que é o comprovante devolvido.
    insert into transacoes (conta_id, tipo, valor, saldo_apos, contraparte_id,
                            estorno_de)
    values (v_original.contraparte_id, 'estorno_saida', v_original.valor,
            v_saldo_outro, p_conta_id, v_contraparte.id);

    insert into transacoes (conta_id, tipo, valor, saldo_apos, contraparte_id,
                            estorno_de)
    values (p_conta_id, 'estorno_entrada', v_original.valor, v_saldo,
            v_original.contraparte_id, p_transacao_id)
    returning id into v_id;
  end if;

  saldo := v_saldo;
  transacao_id := v_id;
end; $$;

comment on function estornar is
  'Cria o lançamento de sinal oposto. O original nunca é alterado.';

revoke execute on function estornar(bigint, bigint, int) from public, anon, authenticated;
