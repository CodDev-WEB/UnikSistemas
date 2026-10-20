import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity, ArrowDownToLine, ArrowRight, Bell, Building2, Check, ChevronDown,
  CircleHelp, FileText, LayoutDashboard, LockKeyhole, LogOut, Plus,
  Search, Settings2, ShieldCheck, Users, UserPlus, UserCog, X,
} from "lucide-react";

type Tenant = { id: string; name: string; slug: string; status: string };
type User = { id: string; tenant_id: string; email: string; full_name: string; role: string; is_active: boolean };
type Client = {
  id: string; legal_name: string; trade_name: string | null; tax_id: string | null;
  email: string | null; phone: string | null; status: "active" | "archived";
  created_at: string | null;
};
type Me = { user: User; tenant: Tenant };
type TokenResponse = { access_token: string; token_type: string; expires_in: number };

async function api<T>(path: string, init: RequestInit = {}, token?: string): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body) headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(path, { ...init, headers });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = typeof payload.detail === "string" ? payload.detail : "Não foi possível concluir a operação.";
    throw new Error(message);
  }
  return payload as T;
}

function initials(name: string) {
  return name.trim().split(/\s+/).slice(0, 2).map(part => part[0]?.toUpperCase() ?? "").join("");
}

function formatDate(value: string | null) {
  if (!value) return "—";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? "—" : new Intl.DateTimeFormat("pt-BR").format(parsed);
}

export default function App() {
  const [token, setToken] = useState(() => sessionStorage.getItem("unik_access_token") ?? "");
  const [me, setMe] = useState<Me | null>(null);
  const [clients, setClients] = useState<Client[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [currentPage, setCurrentPage] = useState<"dashboard" | "clients" | "users">("dashboard");
  const [loginForm, setLoginForm] = useState({ tenant_slug: "", email: "", password: "" });
  const [clientForm, setClientForm] = useState({ legal_name: "", trade_name: "", tax_id: "", email: "", phone: "" });
  const [userForm, setUserForm] = useState({ full_name: "", email: "", password: "", role: "accountant" });
  const [search, setSearch] = useState("");
  const [clientFilter, setClientFilter] = useState<"all" | "active" | "archived">("all");
  const [showCreate, setShowCreate] = useState(false);
  const [loginBusy, setLoginBusy] = useState(false);
  const [clientBusy, setClientBusy] = useState(false);
  const [userBusy, setUserBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const loadWorkspace = useCallback(async (activeToken: string) => {
    setLoading(true);
    try {
      const profile = await api<Me>("/api/v1/me", {}, activeToken);
      const list = await api<Client[]>("/api/v1/clients?limit=100", {}, activeToken);
      const staff = ["owner", "admin"].includes(profile.user.role)
        ? await api<User[]>("/api/v1/users", {}, activeToken)
        : [];
      setMe(profile);
      setClients(list);
      setUsers(staff);
      setError("");
    } catch (err) {
      sessionStorage.removeItem("unik_access_token");
      setToken("");
      setMe(null);
      setClients([]);
      setUsers([]);
      setError(err instanceof Error ? err.message : "Sua sessão não está disponível.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (token) {
      void loadWorkspace(token);
    } else {
      setLoading(false);
      setMe(null);
      setClients([]);
      setUsers([]);
    }
  }, [token, loadWorkspace]);

  const filteredClients = useMemo(() => {
    const query = search.trim().toLocaleLowerCase("pt-BR");
    return clients.filter(client => {
      const matchesStatus = clientFilter === "all" || client.status === clientFilter;
      const haystack = [client.legal_name, client.trade_name ?? "", client.tax_id ?? "", client.email ?? ""]
        .join(" ").toLocaleLowerCase("pt-BR");
      return matchesStatus && (!query || haystack.includes(query));
    });
  }, [clients, clientFilter, search]);

  async function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoginBusy(true);
    setError("");
    try {
      const result = await api<TokenResponse>("/api/v1/auth/token", {
        method: "POST",
        body: JSON.stringify(loginForm),
      });
      sessionStorage.setItem("unik_access_token", result.access_token);
      setToken(result.access_token);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível entrar.");
    } finally {
      setLoginBusy(false);
    }
  }

  async function handleCreateClient(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token) return;
    setClientBusy(true);
    setError("");
    setSuccess("");
    try {
      const payload = {
        legal_name: clientForm.legal_name.trim(),
        trade_name: clientForm.trade_name.trim() || null,
        tax_id: clientForm.tax_id.trim() || null,
        email: clientForm.email.trim() || null,
        phone: clientForm.phone.trim() || null,
        status: "active",
      };
      const created = await api<Client>("/api/v1/clients", {
        method: "POST",
        body: JSON.stringify(payload),
      }, token);
      setClients(previous => [created, ...previous]);
      setClientForm({ legal_name: "", trade_name: "", tax_id: "", email: "", phone: "" });
      setShowCreate(false);
      setCurrentPage("clients");
      setSuccess("Cliente cadastrado com sucesso.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível cadastrar o cliente.");
    } finally {
      setClientBusy(false);
    }
  }



  async function handleCreateUser(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token) return;
    setUserBusy(true);
    setError("");
    setSuccess("");
    try {
      const created = await api<User>("/api/v1/users", {
        method: "POST",
        body: JSON.stringify({
          full_name: userForm.full_name.trim(),
          email: userForm.email.trim().toLowerCase(),
          password: userForm.password,
          role: userForm.role,
        }),
      }, token);
      setUsers(previous => [...previous, created].sort((a, b) => a.full_name.localeCompare(b.full_name, "pt-BR")));
      setUserForm({ full_name: "", email: "", password: "", role: "accountant" });
      setSuccess("Usuário adicionado à equipe.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível adicionar o usuário.");
    } finally {
      setUserBusy(false);
    }
  }

  async function handleUpdateUser(userId: string, patch: { role?: string; is_active?: boolean }) {
    if (!token) return;
    setError("");
    setSuccess("");
    try {
      const updated = await api<User>(`/api/v1/users/${userId}`, {
        method: "PATCH",
        body: JSON.stringify(patch),
      }, token);
      setUsers(previous => previous.map(user => user.id === updated.id ? updated : user));
      setSuccess(patch.is_active === false ? "Acesso do usuário desativado." :
        patch.is_active === true ? "Acesso do usuário reativado." : "Perfil de acesso atualizado.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível atualizar o usuário.");
    }
  }

  function logout() {
    sessionStorage.removeItem("unik_access_token");
    setToken("");
    setMe(null);
    setClients([]);
    setUsers([]);
    setError("");
    setSuccess("");
    setCurrentPage("dashboard");
  }

  if (token && loading && !me) {
    return <main className="login-screen"><section className="login-panel loading-state"><div className="spinner"/><span>Preparando seu espaço de trabalho...</span></section></main>;
  }

  if (!token || !me) {
    return (
      <main className="login-screen">
        <div className="login-decoration decoration-one" />
        <div className="login-decoration decoration-two" />
        <section className="login-panel">
          <div className="brand-lockup">
            <div className="brand-mark"><Building2 size={22} strokeWidth={2.3} /></div>
            <div><span className="brand-name">unik<span>sistemas</span></span><span className="brand-subtitle">GESTÃO CONTÁBIL INTEGRADA</span></div>
          </div>
          <div className="login-copy">
            <div className="eyebrow"><span className="eyebrow-dot" /> AMBIENTE DE TRABALHO</div>
            <h1>Bom ter você<br /><em>por aqui.</em></h1>
            <p>Acesse seu escritório e mantenha a rotina contábil em ordem, com tudo no seu devido lugar.</p>
          </div>
          <form className="login-form" onSubmit={handleLogin}>
            <div className="field">
              <label htmlFor="tenant">Identificador do escritório</label>
              <input id="tenant" autoComplete="organization" placeholder="ex.: escritorio-exemplo" value={loginForm.tenant_slug} onChange={e => setLoginForm({...loginForm, tenant_slug:e.target.value})} required />
            </div>
            <div className="field">
              <label htmlFor="email">E-mail profissional</label>
              <input id="email" type="email" autoComplete="username" placeholder="voce@escritorio.com.br" value={loginForm.email} onChange={e => setLoginForm({...loginForm, email:e.target.value})} required />
            </div>
            <div className="field">
              <label htmlFor="password">Senha</label>
              <input id="password" type="password" autoComplete="current-password" placeholder="Digite sua senha" value={loginForm.password} onChange={e => setLoginForm({...loginForm, password:e.target.value})} required />
            </div>
            {error && <div className="alert alert-error" role="alert">{error}</div>}
            <button className="button button-primary login-submit" type="submit" disabled={loginBusy}>
              {loginBusy ? "Verificando acesso..." : "Entrar no sistema"} {!loginBusy && <ArrowRight size={17} />}
            </button>
            <div className="login-security"><LockKeyhole size={14} /> Acesso autenticado e protegido</div>
          </form>
          <div className="login-footer">UNIKSISTEMAS <span>·</span> PRIMEIRA VERSÃO</div>
        </section>
        <aside className="login-aside">
          <div className="aside-orbit orbit-a" /><div className="aside-orbit orbit-b" />
          <div className="aside-content">
            <div className="aside-overline">MENOS RETRABALHO. MAIS CONTROLE.</div>
            <h2>Sua contabilidade,<br /><span>mais organizada.</span></h2>
            <p>Um espaço de trabalho para acompanhar clientes, centralizar informações e construir uma rotina mais previsível.</p>
            <div className="aside-feature"><span><ShieldCheck size={18} /></span><div><strong>Dados por escritório</strong><small>O acesso respeita o ambiente autenticado.</small></div></div>
            <div className="aside-feature"><span><Activity size={18} /></span><div><strong>Rotina com visibilidade</strong><small>Cadastros e próximos módulos em evolução.</small></div></div>
          </div>
          <div className="aside-bottom"><span>PROJETO EM EVOLUÇÃO</span><span>v0.1.0</span></div>
        </aside>
      </main>
    );
  }

  const activeClients = clients.filter(c => c.status === "active").length;
  const archivedClients = clients.filter(c => c.status === "archived").length;
  const canManageUsers = ["owner", "admin"].includes(me.user.role);
  const roleLabels: Record<string, string> = {
    owner: "Responsável",
    admin: "Administrador",
    accountant: "Contador(a)",
    assistant: "Assistente",
    viewer: "Consulta",
  };

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-lockup sidebar-brand">
          <div className="brand-mark"><Building2 size={20} strokeWidth={2.3} /></div>
          <div><span className="brand-name">unik<span>sistemas</span></span><span className="brand-subtitle">GESTÃO CONTÁBIL</span></div>
        </div>
        <div className="workspace-label">ESCRITÓRIO ATUAL</div>
        <button className="workspace-switch" type="button" disabled title="Escritório definido pela sessão autenticada">
          <div className="workspace-avatar">{initials(me.tenant.name) || "U"}</div>
          <div className="workspace-meta"><strong>{me.tenant.name}</strong><small>{me.tenant.slug}</small></div>
          <ChevronDown size={15} />
        </button>
        <div className="nav-caption">ESPAÇO DE TRABALHO</div>
        <nav className="sidebar-nav" aria-label="Navegação principal">
          <button className={currentPage === "dashboard" ? "nav-item selected" : "nav-item"} onClick={() => setCurrentPage("dashboard")}><LayoutDashboard size={18} /><span>Visão geral</span></button>
          <button className={currentPage === "clients" ? "nav-item selected" : "nav-item"} onClick={() => setCurrentPage("clients")}><Users size={18} /><span>Clientes</span><span className="nav-count">{clients.length}</span></button>
          {canManageUsers && <button className={currentPage === "users" ? "nav-item selected" : "nav-item"} onClick={() => setCurrentPage("users")}><UserCog size={18} /><span>Equipe e acessos</span><span className="nav-count">{users.length}</span></button>}
          <button className="nav-item nav-disabled" type="button" title="Módulo planejado" disabled><ArrowDownToLine size={18} /><span>Importações</span><span className="soon">EM BREVE</span></button>
          <button className="nav-item nav-disabled" type="button" title="Módulo planejado" disabled><FileText size={18} /><span>Documentos</span></button>
          <button className="nav-item nav-disabled" type="button" title="Módulo planejado" disabled><Activity size={18} /><span>Pendências</span></button>
        </nav>
        <div className="sidebar-spacer" />
        <div className="sidebar-note"><div className="note-icon"><ShieldCheck size={16} /></div><div><strong>Seu espaço, seus dados</strong><p>O acesso é restrito ao escritório autenticado.</p></div></div>
        <button className="nav-item nav-bottom" type="button" disabled><Settings2 size={18} /><span>Configurações</span></button>
        <button className="profile-button" onClick={logout} title="Sair do sistema">
          <div className="profile-avatar">{initials(me.user.full_name) || "U"}</div>
          <div className="profile-meta"><strong>{me.user.full_name}</strong><small>{me.user.role === "owner" ? "Responsável" : me.user.role}</small></div>
          <LogOut size={16} />
        </button>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div className="breadcrumb"><span>UnikSistemas</span><span className="crumb-divider">/</span><strong>{currentPage === "dashboard" ? "Visão geral" : currentPage === "clients" ? "Clientes" : "Equipe"}</strong></div>
          <div className="topbar-actions"><span className="environment-tag"><i /> Ambiente de trabalho</span><button className="icon-button" type="button" title="Ajuda" onClick={() => setSuccess("Consulte a documentação da API em /docs no ambiente local.")}><CircleHelp size={18} /></button><button className="icon-button" type="button" title="Notificações — em breve" disabled><Bell size={18} /></button><div className="topbar-avatar">{initials(me.user.full_name)}</div></div>
        </header>
        <div className="page-content">
          {error && <div className="alert alert-error page-alert" role="alert"><span>{error}</span><button onClick={() => setError("")} aria-label="Fechar mensagem"><X size={16}/></button></div>}
          {success && <div className="alert alert-success page-alert" role="status"><Check size={16}/><span>{success}</span><button onClick={() => setSuccess("")} aria-label="Fechar mensagem"><X size={16}/></button></div>}
          {loading ? <div className="loading-state"><div className="spinner"/><span>Preparando seu espaço de trabalho...</span></div> : currentPage === "dashboard" ? (
            <>
              <div className="page-heading">
                <div><div className="eyebrow">TERÇA-FEIRA · ESPAÇO DE TRABALHO</div><h1>Olá, {me.user.full_name.split(" ")[0]} <span className="wave">✳</span></h1><p>Veja o que está acontecendo no seu escritório.</p></div>
                <button className="button button-primary" onClick={() => {setShowCreate(true);setCurrentPage("clients");}}><Plus size={17}/> Novo cliente</button>
              </div>
              <section className="metric-grid">
                <div className="metric-card"><div className="metric-top"><span>Total de clientes</span><div className="metric-icon icon-indigo"><Users size={18}/></div></div><div className="metric-value">{clients.length.toString().padStart(2,"0")}</div><div className="metric-foot"><span className="metric-neutral">Base cadastrada</span><span className="metric-foot-label">CLIENTES</span></div></div>
                <div className="metric-card"><div className="metric-top"><span>Cadastros ativos</span><div className="metric-icon icon-green"><Check size={18}/></div></div><div className="metric-value">{activeClients.toString().padStart(2,"0")}</div><div className="metric-foot"><span className="metric-positive"><i/> Em operação</span><span className="metric-foot-label">ATIVOS</span></div></div>
                <div className="metric-card"><div className="metric-top"><span>Arquivados</span><div className="metric-icon icon-amber"><FileText size={18}/></div></div><div className="metric-value">{archivedClients.toString().padStart(2,"0")}</div><div className="metric-foot"><span className="metric-neutral">Fora da rotina ativa</span><span className="metric-foot-label">ARQUIVO</span></div></div>
              </section>
              <section className="content-card">
                <div className="card-heading"><div><h2>Clientes recentes</h2><p>Um panorama dos últimos cadastros do escritório.</p></div><button className="text-button" onClick={() => setCurrentPage("clients")}>Ver todos <ArrowRight size={15}/></button></div>
                {clients.length === 0 ? <EmptyClients onAdd={() => {setCurrentPage("clients");setShowCreate(true);}} /> : <ClientTable clients={clients.slice(0,5)} onOpen={() => setCurrentPage("clients")} />}
              </section>
              <section className="next-step-card"><div className="next-step-icon"><Activity size={20}/></div><div><span className="next-step-label">PRÓXIMA ETAPA</span><h3>Organize a base de atendimento</h3><p>Cadastre as empresas atendidas pelo escritório. Importações e acompanhamento de pendências serão adicionados nas próximas entregas.</p></div><button className="button button-secondary" onClick={() => setCurrentPage("clients")}>Abrir clientes <ArrowRight size={16}/></button></section>
            </>
          ) : currentPage === "clients" ? (
            <>
              <div className="page-heading">
                <div><div className="eyebrow">CADASTROS · BASE DE ATENDIMENTO</div><h1>Clientes</h1><p>Gerencie as empresas atendidas pelo seu escritório.</p></div>
                <button className="button button-primary" onClick={() => setShowCreate(v => !v)}><Plus size={17}/>{showCreate ? "Fechar cadastro" : "Novo cliente"}</button>
              </div>
              {showCreate && <section className="content-card create-card"><div className="card-heading"><div><h2>Novo cliente</h2><p>Preencha os dados principais da empresa. O tenant é definido pelo seu acesso.</p></div><button className="icon-button" onClick={() => setShowCreate(false)} aria-label="Fechar"><X size={18}/></button></div><form className="client-form" onSubmit={handleCreateClient}><div className="field field-wide"><label htmlFor="legal-name">Razão social *</label><input id="legal-name" value={clientForm.legal_name} onChange={e => setClientForm({...clientForm,legal_name:e.target.value})} required minLength={2} maxLength={200} placeholder="Nome empresarial completo"/></div><div className="field"><label htmlFor="trade-name">Nome fantasia</label><input id="trade-name" value={clientForm.trade_name} onChange={e => setClientForm({...clientForm,trade_name:e.target.value})} maxLength={200} placeholder="Nome comercial"/></div><div className="field"><label htmlFor="tax-id">CNPJ ou identificador fiscal</label><input id="tax-id" value={clientForm.tax_id} onChange={e => setClientForm({...clientForm,tax_id:e.target.value})} maxLength={32} placeholder="00.000.000/0000-00"/></div><div className="field"><label htmlFor="client-email">E-mail</label><input id="client-email" type="email" value={clientForm.email} onChange={e => setClientForm({...clientForm,email:e.target.value})} placeholder="contato@empresa.com.br"/></div><div className="field"><label htmlFor="client-phone">Telefone</label><input id="client-phone" value={clientForm.phone} onChange={e => setClientForm({...clientForm,phone:e.target.value})} maxLength={32} placeholder="(00) 00000-0000"/></div><div className="form-actions"><span className="form-hint">* Campo obrigatório</span><button type="button" className="button button-secondary" onClick={() => setShowCreate(false)}>Cancelar</button><button type="submit" className="button button-primary" disabled={clientBusy}>{clientBusy ? "Salvando..." : "Salvar cliente"} {!clientBusy && <Check size={16}/>}</button></div></form></section>}
              <section className="content-card">
                <div className="client-toolbar"><div className="search-box"><Search size={17}/><input value={search} onChange={e => setSearch(e.target.value)} placeholder="Buscar por empresa, CNPJ ou e-mail..." aria-label="Buscar clientes"/>{search && <button onClick={() => setSearch("")} aria-label="Limpar busca"><X size={15}/></button>}</div><div className="filter-group" aria-label="Filtrar por status"><button className={clientFilter === "all" ? "filter active" : "filter"} onClick={() => setClientFilter("all")}>Todos <span>{clients.length}</span></button><button className={clientFilter === "active" ? "filter active" : "filter"} onClick={() => setClientFilter("active")}>Ativos</button><button className={clientFilter === "archived" ? "filter active" : "filter"} onClick={() => setClientFilter("archived")}>Arquivados</button></div></div>
                {filteredClients.length === 0 ? <EmptyClients onAdd={() => {setShowCreate(true);setClientFilter("all");setSearch("");}} noResults={clients.length > 0}/> : <ClientTable clients={filteredClients} />}
                <div className="table-footer"><span>Exibindo <strong>{filteredClients.length}</strong> de <strong>{clients.length}</strong> clientes</span><span>Dados do escritório autenticado</span></div>
              </section>
            </>
          ) : (
            <>
              <div className="page-heading">
                <div><div className="eyebrow">SEGURANÇA · CONTROLE DE ACESSO</div><h1>Equipe e acessos</h1><p>Gerencie quem pode acessar este escritório e quais atividades cada pessoa pode realizar.</p></div>
              </div>
              <section className="role-explainer">
                <div><ShieldCheck size={20}/><div><strong>Responsável</strong><span>Controle integral do escritório e dos usuários.</span></div></div>
                <div><UserCog size={20}/><div><strong>Administrador</strong><span>Gerencia a equipe, exceto outros administradores e o responsável.</span></div></div>
                <div><Users size={20}/><div><strong>Contador(a) / Assistente</strong><span>Acessa e cadastra clientes.</span></div></div>
                <div><LockKeyhole size={20}/><div><strong>Consulta</strong><span>Visualiza clientes, sem cadastrar ou alterar usuários.</span></div></div>
              </section>
              <section className="content-card create-card">
                <div className="card-heading"><div><h2>Adicionar à equipe</h2><p>Crie um usuário no escritório atual. A senha inicial deve ser entregue por um canal seguro.</p></div><div className="team-card-icon"><UserPlus size={18}/></div></div>
                <form className="client-form" onSubmit={handleCreateUser}>
                  <div className="field"><label htmlFor="user-full-name">Nome completo *</label><input id="user-full-name" value={userForm.full_name} onChange={e => setUserForm({...userForm, full_name:e.target.value})} required minLength={2} maxLength={160} placeholder="Nome do colaborador"/></div>
                  <div className="field"><label htmlFor="user-email">E-mail de acesso *</label><input id="user-email" type="email" value={userForm.email} onChange={e => setUserForm({...userForm, email:e.target.value})} required maxLength={254} placeholder="colaborador@escritorio.com.br"/></div>
                  <div className="field"><label htmlFor="user-password">Senha inicial *</label><input id="user-password" type="password" autoComplete="new-password" value={userForm.password} onChange={e => setUserForm({...userForm, password:e.target.value})} required minLength={12} maxLength={128} placeholder="Mínimo de 12 caracteres"/></div>
                  <div className="field"><label htmlFor="user-role">Perfil de acesso *</label><select id="user-role" value={userForm.role} onChange={e => setUserForm({...userForm, role:e.target.value})}>{me.user.role === "owner" && <option value="admin">Administrador</option>}<option value="accountant">Contador(a)</option><option value="assistant">Assistente</option><option value="viewer">Consulta (somente leitura)</option></select></div>
                  <div className="form-actions"><span className="form-hint">A senha é armazenada como hash; nunca aparece na lista.</span><button type="submit" className="button button-primary" disabled={userBusy}>{userBusy ? "Adicionando..." : "Adicionar usuário"} {!userBusy && <UserPlus size={16}/>}</button></div>
                </form>
              </section>
              <section className="content-card">
                <div className="card-heading"><div><h2>Usuários do escritório</h2><p>{users.length} pessoa(s) vinculada(s) a {me.tenant.name}.</p></div><span className="security-chip"><ShieldCheck size={14}/> Isolamento por escritório</span></div>
                {users.length === 0 ? <div className="empty-state"><div className="empty-illustration"><Users size={26}/></div><h3>Nenhum usuário encontrado</h3><p>Os usuários serão exibidos aqui depois que forem cadastrados.</p></div> : <div className="team-list">{users.map(user => {
                  const isSelf = user.id === me.user.id;
                  const canEditUser = !isSelf && user.role !== "owner" && !(me.user.role === "admin" && user.role === "admin");
                  const canEditRole = canEditUser;
                  const roleOptions = me.user.role === "owner"
                    ? [{value:"admin",label:"Administrador"},{value:"accountant",label:"Contador(a)"},{value:"assistant",label:"Assistente"},{value:"viewer",label:"Consulta"}]
                    : [{value:"accountant",label:"Contador(a)"},{value:"assistant",label:"Assistente"},{value:"viewer",label:"Consulta"}];
                  return <div className="team-row" key={user.id}>
                    <div className="team-avatar">{initials(user.full_name)}</div>
                    <div className="team-person"><strong>{user.full_name}{isSelf && <span className="you-label">VOCÊ</span>}</strong><small>{user.email}</small></div>
                    <div className="team-role">{user.role === "owner" || !canEditRole ? <span className="role-pill">{roleLabels[user.role] || user.role}</span> : <select aria-label={`Perfil de ${user.full_name}`} value={user.role} onChange={e => void handleUpdateUser(user.id, {role:e.target.value})}>{roleOptions.map(role => <option key={role.value} value={role.value}>{role.label}</option>)}</select>}</div>
                    <span className={user.is_active ? "status-pill status-active" : "status-pill status-archived"}><i/>{user.is_active ? "Ativo" : "Desativado"}</span>
                    {canEditUser ? <button className={user.is_active ? "button button-secondary team-action" : "button button-primary team-action"} onClick={() => void handleUpdateUser(user.id, {is_active:!user.is_active})}>{user.is_active ? "Desativar acesso" : "Reativar acesso"}</button> : <span className="team-protected"><LockKeyhole size={13}/> Protegido</span>}
                  </div>;
                })}</div>}
              </section>
              <p className="permissions-note"><LockKeyhole size={14}/> As permissões são verificadas pela API. Alterar a interface não concede acesso adicional; operações fora do perfil são recusadas pelo servidor.</p>
            </>
          )}
          <footer className="page-footer"><span>© 2026 UnikSistemas</span><span>GESTÃO CONTÁBIL · VERSÃO 0.1.0</span></footer>
        </div>
      </main>
    </div>
  );
}

function EmptyClients({ onAdd, noResults = false }: { onAdd: () => void; noResults?: boolean }) {
  return <div className="empty-state"><div className="empty-illustration"><Building2 size={26}/></div><h3>{noResults ? "Nenhum resultado encontrado" : "Sua base começa aqui"}</h3><p>{noResults ? "Tente ajustar a busca ou alterar o filtro selecionado." : "Cadastre a primeira empresa atendida pelo escritório para começar a organizar sua base."}</p>{!noResults && <button className="button button-primary" onClick={onAdd}><Plus size={16}/> Cadastrar primeiro cliente</button>}</div>;
}

function ClientTable({ clients, onOpen }: { clients: Client[]; onOpen?: () => void }) {
  return <div className="table-wrap"><table className="clients-table"><thead><tr><th>EMPRESA</th><th>IDENTIFICADOR FISCAL</th><th>CONTATO</th><th>CADASTRO</th><th>STATUS</th>{onOpen && <th/>}</tr></thead><tbody>{clients.map(client => <tr key={client.id}><td><div className="company-cell"><div className="company-avatar">{initials(client.trade_name || client.legal_name)}</div><div className="company-name"><strong>{client.trade_name || client.legal_name}</strong><small>{client.trade_name ? client.legal_name : "Cadastro empresarial"}</small></div></div></td><td className="mono-cell">{client.tax_id || "—"}</td><td><div className="contact-cell">{client.email || "Sem e-mail"}{client.phone && <small>{client.phone}</small>}</div></td><td>{formatDate(client.created_at)}</td><td><span className={client.status === "active" ? "status-pill status-active" : "status-pill status-archived"}><i/>{client.status === "active" ? "Ativo" : "Arquivado"}</span></td>{onOpen && <td><button className="row-open" onClick={onOpen} aria-label="Abrir todos os clientes"><ArrowRight size={16}/></button></td>}</tr>)}</tbody></table></div>;
}
