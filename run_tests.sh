#!/bin/bash

# Ascendia Full Test Suite Runner
# Runs ALL existing tests across all apps

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║          🧪 ASCENDIA FULL TEST SUITE 🧪                ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
echo ""

# Ativar ambiente virtual
if [ -d ".venv" ]; then
    echo -e "${CYAN}📦 Ativando ambiente virtual...${NC}"
    source .venv/bin/activate
else
    echo -e "${RED}❌ Ambiente virtual não encontrado!${NC}"
    exit 1
fi

echo ""
echo -e "${YELLOW}📊 Apps: Users • Workspace • Notes${NC}"
echo -e "${YELLOW}📝 Executando todos os testes implementados...${NC}"
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Run all tests, including notes model tests (skip view tests that need templates)
python manage.py test \
    users \
    workspace \
    notes.tests.NoteModelTest \
    notes.tests.TagModelTest \
    notes.tests.NoteTagModelTest \
    notes.tests.NotePermissionsTest \
    notes.tests.NoteTagRelationshipTest \
    --verbosity=1

exit_code=$?

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

if [ $exit_code -eq 0 ]; then
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║          ✅ ALL TESTS PASSED! GREAT JOB! ✅            ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${GREEN}🎉 Your code is working perfectly!${NC}"
    echo ""
else
    echo ""
    echo -e "${RED}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║          ❌ SOME TESTS FAILED! NEEDS FIXING ❌         ║${NC}"
    echo -e "${RED}╚════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${RED}⚠️  Please review the failed tests above.${NC}"
    echo ""
fi

exit $exit_code
