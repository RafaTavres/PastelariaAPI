#Rafael dos Santos Tavares

from fastapi import APIRouter, Depends, HTTPException, status, Request
from services.AuditoriaService import AuditoriaService
from infra.rate_limit import limiter, get_rate_limit
from sqlalchemy.orm import Session
from typing import List
from domain.schemas.AuthSchema import FuncionarioAuth
from domain.schemas.ProdutoSchema import (
    ProdutoCreate, 
    ProdutoResponse, 
    ProdutoUpdate,
    ProdutoPublicResponse
)
from infra.dependencies import get_current_active_user, require_group
from infra.orm.ProdutoModel import ProdutoDB
from infra.database import get_db
router = APIRouter()

# Criar as rotas/endpoints: GET, POST, PUT, DELETE
@router.get("/produtos-publica/", response_model=List[ProdutoPublicResponse], tags=["Produto"], status_code=status.HTTP_200_OK)
@limiter.limit(get_rate_limit("moderate"))
async def get_produto(
        request: Request,
        db: Session = Depends(get_db)
    ):
    """Retorna todos os produtos"""
    try:
        produtos = db.query(ProdutoDB).all()
        return produtos
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar produtos: {str(e)}"
        )
    
@router.get("/produto/", response_model=List[ProdutoResponse], tags=["Produto"], status_code=status.HTTP_200_OK)
@limiter.limit(get_rate_limit("moderate"))
async def get_produto(
        request: Request,
        db: Session = Depends(get_db),
        current_user: FuncionarioAuth = Depends(get_current_active_user)
    ):
    """Retorna todos os produtos"""
    try:
        produtos = db.query(ProdutoDB).all()
        return produtos
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar produtos: {str(e)}"
        )

@router.get("/produto/{id}", response_model=ProdutoResponse, tags=["Produto"], status_code=status.HTTP_200_OK)
@limiter.limit(get_rate_limit("moderate"))
async def get_produto(
        request: Request,
        id: int, 
        db: Session = Depends(get_db),
        current_user: FuncionarioAuth = Depends(get_current_active_user)
    ):
    """Retorna um produto específico pelo ID"""
    try:
        produto = db.query(ProdutoDB).filter(ProdutoDB.id == id).first()
        if not produto:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produto não encontrado")
        
        return produto
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Erro ao buscar produto: {str(e)}"
        )

@router.post("/produto/", response_model=ProdutoResponse, tags=["Produto"], status_code=status.HTTP_201_CREATED)
@limiter.limit(get_rate_limit("moderate"))
async def post_produto(
        request: Request,
        produto_data: ProdutoCreate,
        db: Session = Depends(get_db),
        current_user: FuncionarioAuth = Depends(require_group([1]))
    ):
    """Cria um novo produto"""
    existing_produto = db.query(ProdutoDB).filter(ProdutoDB.nome == produto_data.nome).first()
    if existing_produto:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Já existe um produto com este nome"
        )
    try:
        novo_produto = ProdutoDB(
            id=None,
            nome=produto_data.nome,
            descricao=produto_data.descricao,
            foto=produto_data.foto,
            valor_unitario=produto_data.valor_unitario
        )
        db.add(novo_produto)
        db.commit()
        db.refresh(novo_produto)

        AuditoriaService.registrar_acao(
            db=db,
            funcionario_id=current_user.id,
            acao="CREATE",
            recurso="PRODUTO",
            recurso_id=novo_produto.id,
            dados_antigos=None,
            dados_novos=novo_produto, # Objeto SQLAlchemy com dados novos
            request=request # Request completo para capturar IP e user agent
        )
        return novo_produto
    
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao criar produto: {str(e)}"
        )

@router.put("/produto/{id}", response_model=ProdutoResponse, tags=["Produto"], status_code=status.HTTP_200_OK)
@limiter.limit(get_rate_limit("moderate"))
async def put_produto(
        request: Request,
        id: int, 
        produto_data: ProdutoUpdate, 
        db: Session = Depends(get_db),
        current_user: FuncionarioAuth = Depends(require_group([1]))
    ):
    """Atualiza um produto"""
    try:
        produto = db.query(ProdutoDB).filter(ProdutoDB.id == id).first()
        if not produto:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produto não encontrado")

        # Atualiza os campos do produto
        produto.nome = produto_data.nome
        produto.descricao = produto_data.descricao
        produto.foto = produto_data.foto
        produto.valor_unitario = produto_data.valor_unitario

        dados_antigos_obj = produto.__dict__.copy()

        db.commit()
        db.refresh(produto)

        AuditoriaService.registrar_acao(
            db=db,
            funcionario_id=current_user.id,
            acao="UPDATE",
            recurso="PRODUTO",
            recurso_id=produto.id,
            dados_antigos=dados_antigos_obj, # Objeto SQLAlchemy com dados antigos
            dados_novos=produto, # Objeto SQLAlchemy com dados novos
            request=request # Request completo para capturar IP e user agent
        )
        return produto
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao atualizar produto: {str(e)}"
        )

@router.delete("/produto/{id}", response_model=ProdutoResponse, tags=["Produto"], status_code=status.HTTP_200_OK)
@limiter.limit(get_rate_limit("moderate"))
async def delete_produto(
        request: Request,
        id: int, 
        db: Session = Depends(get_db),
        current_user: FuncionarioAuth = Depends(require_group([1]))
    ):
    """Exclui um produto"""
    try:
        produto = db.query(ProdutoDB).filter(ProdutoDB.id == id).first()
        if not produto:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produto não encontrado")

        db.delete(produto)
        db.commit()

        AuditoriaService.registrar_acao(
            db=db,
            funcionario_id=current_user.id,
            acao="DELETE",
            recurso="PRODUTO",
            recurso_id=produto.id,
            dados_antigos=produto,
            dados_novos=None,
            request=request
        )
        
        return produto
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao excluir produto: {str(e)}"
        )