#Rafael dos Santos Tavares
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from services.AuditoriaService import AuditoriaService
from infra.rate_limit import limiter, get_rate_limit
from slowapi.errors import RateLimitExceeded
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from typing import List, Optional

from domain.schemas.AuthSchema import FuncionarioAuth

from domain.schemas.FuncionarioSchema import (
    FuncionarioCreate,
    FuncionarioUpdate,
    FuncionarioResponse
)

from infra.dependencies import get_current_active_user, require_group
from infra.security import get_password_hash
from infra.orm.FuncionarioModel import FuncionarioDB
from infra.database import get_async_db

router = APIRouter()

# Criar as rotas/endpoints: GET, POST, PUT, DELETE
@router.get("/funcionario/", response_model=List[FuncionarioResponse], tags=["Funcionário"], status_code=status.HTTP_200_OK)
@limiter.limit(get_rate_limit("moderate"))
async def get_funcionario(
    request: Request,
    skip: int = Query(0, ge=0, description="Número de registros para pular"), # ge = maior ou igual
    limit: int = Query(100, ge=1, le=1000, description="Número máximo de registros"), # ge = maior ou igual, le = menor ou igual
    id: Optional[int] = Query(None, description="Filtrar por ID"),
    nome: Optional[str] = Query(None, description="Filtrar por nome"),
    matricula: Optional[str] = Query(None, description="Filtrar por matrícula"),
    cpf: Optional[str] = Query(None, description="Filtrar por CPF"),
    grupo: Optional[str] = Query(None, description="Filtrar por grupo: 1=Admin, 2=Balcão, 3=Caixa - Separar por vírgula"),
    telefone: Optional[str] = Query(None, description="Filtrar por telefone"),
    db: Session = Depends(get_async_db),
    current_user: FuncionarioAuth = Depends(require_group([1]))
):
    """Retorna todos os funcionários"""
    try:
        result = await db.execute(select(FuncionarioDB))
        funcionarios = result.scalars().all()
        return funcionarios
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar funcionários: {str(e)}"
        )

@router.get("/funcionario/{id}", response_model=FuncionarioResponse, tags=["Funcionário"], status_code=status.HTTP_200_OK)
@limiter.limit(get_rate_limit("critical"))
async def get_funcionario(
        request: Request,
        id: int, db: Session = Depends(get_async_db),
        current_user: FuncionarioAuth = Depends(get_current_active_user)         
    ):
    """Retorna um funcionário específico pelo ID"""
    try:
        result = await db.execute(select(FuncionarioDB).filter(FuncionarioDB.id == id))
        funcionario = result.scalar_one_or_none()
        if not funcionario:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Funcionário não encontrado")
        
        return funcionario
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Erro ao buscar funcionário: {str(e)}"
        )

@router.post("/funcionario/", response_model=FuncionarioResponse, status_code=status.HTTP_201_CREATED, tags=["Funcionário"])
@limiter.limit(get_rate_limit("restrictive"))
async def post_funcionario(
        request: Request,
        funcionario_data: FuncionarioCreate,
        db: Session = Depends(get_async_db),
        current_user: FuncionarioAuth = Depends(require_group([1]))
    ):
    """Cria um novo funcionário"""
    try:
        # Verifica se já existe funcionário com este CPF
        result = await db.execute(select(FuncionarioDB).filter(FuncionarioDB.cpf == funcionario_data.cpf))
        existing_funcionario = result.scalar_one_or_none()
        if existing_funcionario:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Já existe um funcionário com este CPF"
            )
        # Cria o novo funcionário
        hashed_password = get_password_hash(funcionario_data.senha)
        novo_funcionario = FuncionarioDB(
            id=None, # Será auto-incrementado
            nome=funcionario_data.nome,
            matricula=funcionario_data.matricula,
            cpf=funcionario_data.cpf,
            telefone=funcionario_data.telefone,
            grupo=funcionario_data.grupo,
            senha=hashed_password
        )
        db.add(novo_funcionario)
        await db.commit()
        await db.refresh(novo_funcionario)

        AuditoriaService.registrar_acao(
            db=db,
            funcionario_id=current_user.id,
            acao="CREATE",
            recurso="FUNCIONARIO",
            recurso_id=novo_funcionario.id,
            dados_antigos=None,
            dados_novos=novo_funcionario, # Objeto SQLAlchemy com dados novos
            request=request # Request completo para capturar IP e user agent
        )
        return novo_funcionario
    
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao criar funcionário: {str(e)}"
        )

@router.put("/funcionario/{id}", response_model=FuncionarioResponse, tags=["Funcionário"], status_code=status.HTTP_200_OK)
@limiter.limit(get_rate_limit("restrictive"))
async def put_funcionario(
        request: Request,
        id: int, 
        funcionario_data: FuncionarioUpdate, 
        db: Session = Depends(get_async_db),
        current_user: FuncionarioAuth = Depends(require_group([1]))
    ):
    """Atualiza um funcionário existente"""
    try:
        result = await db.execute(select(FuncionarioDB).filter(FuncionarioDB.id == id))
        funcionario = result.scalar_one_or_none()
        if not funcionario:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Funcionário não encontrado"
            )
        # Verifica se está tentando atualizar para um CPF que já existe
        existing_funcionario = None
        if funcionario_data.cpf and funcionario_data.cpf != funcionario.cpf:
            result = await db.execute(select(FuncionarioDB).filter(FuncionarioDB.cpf == funcionario_data.cpf))
            existing_funcionario = result.scalar_one_or_none()
        if existing_funcionario:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Já existe um funcionário com este CPF"
            )
        
        if funcionario_data.senha:
            funcionario_data.senha = get_password_hash(funcionario_data.senha)

        if funcionario_data.grupo:
            if funcionario_data.grupo not in [1, 2, 3]:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Grupo inválido. Apenas grupos 1 (Admin), 2 (Atendimento Balcão) ou 3 (Atendimento Caixa) são permitidos.")
            # armazena uma copia do objeto com os dados atuais, para salvar na auditoria
            # não pode manter referencia com funcionário, para que o auditoria possa comparar
            # por isso a cópia do __dict__
            dados_antigos_obj = funcionario.__dict__.copy()

        # Atualiza apenas os campos fornecidos
        update_data = funcionario_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(funcionario, field, value)

        await db.commit()
        await db.refresh(funcionario)

        AuditoriaService.registrar_acao(
            db=db,
            funcionario_id=current_user.id,
            acao="UPDATE",
            recurso="FUNCIONARIO",
            recurso_id=funcionario.id,
            dados_antigos=dados_antigos_obj, # Objeto SQLAlchemy com dados antigos
            dados_novos=funcionario, # Objeto SQLAlchemy com dados novos
            request=request # Request completo para capturar IP e user agent
        )

        return funcionario
    
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao atualizar funcionário: {str(e)}"
        )

@router.delete("/funcionario/{id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Funcionário"], summary="Remover funcionário")
async def delete_funcionario(
        request: Request,
        id: int, 
        db: Session = Depends(get_async_db),
        current_user: FuncionarioAuth = Depends(require_group([1]))
    ):
    """Remove um funcionário"""
    try:
        result = await db.execute(select(FuncionarioDB).filter(FuncionarioDB.id == id))
        funcionario = result.scalar_one_or_none()
        if not funcionario:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Funcionário não encontrado"
            )
            
        await db.delete(funcionario)
        await db.commit()

        AuditoriaService.registrar_acao(
            db=db,
            funcionario_id=current_user.id,
            acao="DELETE",
            recurso="FUNCIONARIO",
            recurso_id=funcionario.id,
            dados_antigos=funcionario,
            dados_novos=None,
            request=request
        )
        
        return None
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao deletar funcionário: {str(e)}"
        )