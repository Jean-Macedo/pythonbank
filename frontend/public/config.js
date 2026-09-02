// Configuração de tempo de execução.
//
// Em desenvolvimento este arquivo fica vazio e vale o `.env` do Vite. Na
// imagem Docker, o entrypoint do nginx reescreve este arquivo na subida do
// container com o valor de `API_URL`.
//
// Existe porque o Vite embute `import.meta.env` **na compilação**: o valor vira
// literal no bundle. Passar VITE_API_URL como variável de ambiente do container
// não teria efeito nenhum — e falharia em silêncio, que é o pior jeito de
// falhar.
window.__BANCO_CONFIG__ = {}
