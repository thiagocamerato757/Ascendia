#!/bin/bash
# Script para executar testes do Ascendia
# Uso: ./run_tests.sh [opções]

# Cores para output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}🧪 Ascendia Test Runner${NC}"
echo -e "${BLUE}======================${NC}\n"

# Ativar ambiente virtual
if [ -d ".venv" ]; then
    echo -e "${YELLOW}📦 Ativando ambiente virtual...${NC}"
    source .venv/bin/activate
else
    echo -e "${RED}❌ Ambiente virtual não encontrado!${NC}"
    exit 1
fi

# Função para executar testes
run_tests() {
    local verbose=$1
    local specific_test=$2
    
    if [ -n "$specific_test" ]; then
        echo -e "${YELLOW}🎯 Executando teste específico: $specific_test${NC}\n"
        python manage.py test users.tests.$specific_test $verbose
    else
        echo -e "${YELLOW}🎯 Executando todos os testes...${NC}\n"
        python manage.py test users $verbose
    fi
    
    exit_code=$?
    
    if [ $exit_code -eq 0 ]; then
        echo -e "\n${GREEN}✅ Todos os testes passaram!${NC}"
    else
        echo -e "\n${RED}❌ Alguns testes falharam!${NC}"
    fi
    
    return $exit_code
}

# Processar argumentos
case "$1" in
    -v|--verbose)
        echo -e "${BLUE}Modo: Verbose${NC}"
        run_tests "-v 2" "$2"
        ;;
    -h|--help)
        echo "Uso: ./run_tests.sh [opções] [teste-específico]"
        echo ""
        echo "Opções:"
        echo "  (nenhuma)       Executar todos os testes"
        echo "  -v, --verbose   Executar com output detalhado"
        echo "  -h, --help      Mostrar esta mensagem"
        echo ""
        echo "Exemplos:"
        echo "  ./run_tests.sh                              # Todos os testes"
        echo "  ./run_tests.sh -v                           # Todos os testes (verbose)"
        echo "  ./run_tests.sh ProfileModelTests            # Classe específica"
        echo "  ./run_tests.sh -v ProfileModelTests         # Classe específica (verbose)"
        echo ""
        echo "Classes de Teste Disponíveis:"
        echo "  - ProfileModelTests"
        echo "  - SignUpFormTests"
        echo "  - UserUpdateFormTests"
        echo "  - ProfileUpdateFormTests"
        echo "  - SignUpViewTests"
        echo "  - LoginViewTests"
        echo "  - ProfileViewTests"
        echo "  - AvatarUpdateTests"
        echo "  - LogoutTests"
        echo "  - HomeViewTests"
        ;;
    "")
        run_tests "" ""
        ;;
    *)
        echo -e "${BLUE}Executando teste: $1${NC}"
        run_tests "" "$1"
        ;;
esac
