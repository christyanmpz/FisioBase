import { useEffect, useState, type FormEvent, type ReactNode } from 'react';
import { Activity, ArrowRight, CalendarDays, Check, CircleAlert, ClipboardList, Eye, EyeOff, LayoutDashboard, LockKeyhole, LogOut, ShieldCheck, Stethoscope, Users, X } from 'lucide-react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ErrorBoundary } from '@/components/error-boundary';
import { Toaster } from '@/components/ui/toaster';
import { TooltipProvider } from '@/components/ui/tooltip';
import NotFound from '@/pages/not-found';
import { Link, Route, Switch, Router as WouterRouter, useLocation } from 'wouter';

type UserRole = 'admin' | 'fisioterapeuta';

type User = {
  id: number;
  nome: string;
  email: string;
  senha: string;
  tipo_usuario: UserRole;
};

const DEMO_USERS: User[] = [
  { id: 1, nome: 'Marina Costa', email: 'admin@fisio.com', senha: 'Admin@123', tipo_usuario: 'admin' },
  { id: 2, nome: 'Rafael Lima', email: 'fisio@fisio.com', senha: 'Fisio@123', tipo_usuario: 'fisioterapeuta' },
];

const queryClient = new QueryClient();

function initials(nome: string) {
  return nome.split(' ').slice(0, 2).map((part) => part[0]).join('').toUpperCase();
}

function firstName(nome: string) {
  return nome.split(' ')[0];
}

function dashboardPath(tipo: UserRole) {
  return tipo === 'admin' ? '/dashboard/admin' : '/dashboard/fisioterapeuta';
}

function Brand({ small = false }: { small?: boolean }) {
  return (
    <span className={small ? 'fb-brand-mark fb-brand-mark--small' : 'fb-brand-mark'} aria-hidden="true" />
  );
}

function LoginPage({ onLogin }: { onLogin: (user: User) => void }) {
  const [email, setEmail] = useState('');
  const [senha, setSenha] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [, setLocation] = useLocation();

  const fillDemo = (user: User) => {
    setEmail(user.email);
    setSenha(user.senha);
    setError('');
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setIsSubmitting(true);
    const match = DEMO_USERS.find((user) => user.email.toLowerCase() === email.trim().toLowerCase() && user.senha === senha);
    window.setTimeout(() => {
      setIsSubmitting(false);
      if (!match) {
        setError('Não encontramos uma conta com esses dados. Confira o e-mail e a senha.');
        return;
      }
      onLogin(match);
      setLocation(dashboardPath(match.tipo_usuario));
    }, 220);
  };

  return (
    <main className="login-shell fb-page fb-noise" id="conteudo">
      <section className="login-intro fb-reveal" aria-labelledby="brand-title">
        <Brand />
        <p className="fb-kicker">Gestão clínica inteligente</p>
        <h1 id="brand-title" className="fb-display">Cuidado em movimento.</h1>
        <p className="login-intro-copy">
          Uma base simples e segura para organizar o dia a dia do seu consultório de fisioterapia.
        </p>
        <div className="login-note">
          <span aria-hidden="true">+</span>
          <span>Feito para profissionais que cuidam de pessoas.</span>
        </div>
      </section>

      <section className="login-panel fb-reveal fb-reveal-delay-1" aria-labelledby="login-title">
        <div className="login-card">
          <div className="login-heading">
            <p className="fb-kicker" style={{ color: 'hsl(var(--muted-foreground))' }}>Acesso restrito</p>
            <h2 id="login-title" className="fb-display">Olá, que bom ter você aqui.</h2>
            <p>Entre com suas credenciais para acessar o FisioBase.</p>
          </div>

          <div className="fb-alert fb-alert--info" role="status" data-testid="status-demo-mode">
            <Activity size={16} aria-hidden="true" />
            <span>Demonstração local ativa. A conexão com o Flask será adicionada na próxima etapa.</span>
          </div>

          {error && (
            <div className="fb-alert fb-alert--error" role="alert" data-testid="alert-login-error">
              <CircleAlert size={16} aria-hidden="true" />
              <span>{error}</span>
            </div>
          )}

          <form className="fb-form" onSubmit={handleSubmit}>
            <div className="fb-field">
              <label htmlFor="email">E-mail</label>
              <input
                id="email"
                className="fb-input"
                data-testid="input-email"
                name="email"
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                autoComplete="username"
                placeholder="seu@email.com"
                required
                autoFocus
              />
            </div>
            <div className="fb-field">
              <div className="fb-label-row">
                <label htmlFor="senha" className="fb-field-label">Senha</label>
                <span className="fb-hint">Obrigatória</span>
              </div>
              <div className="fb-password-wrap">
                <input
                  id="senha"
                  className="fb-input"
                  data-testid="input-password"
                  name="senha"
                  type={showPassword ? 'text' : 'password'}
                  value={senha}
                  onChange={(event) => setSenha(event.target.value)}
                  autoComplete="current-password"
                  placeholder="Digite sua senha"
                  required
                />
                <button
                  type="button"
                  className="fb-password-toggle"
                  data-testid="button-toggle-password"
                  aria-label={showPassword ? 'Ocultar senha' : 'Mostrar senha'}
                  aria-pressed={showPassword}
                  onClick={() => setShowPassword((visible) => !visible)}
                >
                  {showPassword ? <><EyeOff size={13} aria-hidden="true" /> Ocultar</> : <><Eye size={13} aria-hidden="true" /> Mostrar</>}
                </button>
              </div>
            </div>
            <button className="fb-button fb-button--primary fb-button--full" data-testid="button-submit-login" type="submit" disabled={isSubmitting}>
              {isSubmitting ? 'Verificando acesso' : 'Entrar no sistema'}
              {!isSubmitting && <ArrowRight size={17} aria-hidden="true" />}
            </button>
          </form>

          <div className="demo-access" aria-label="Acessos de demonstração" data-testid="panel-demo-access">
            <p className="demo-access-title">Acessos de demonstração</p>
            <button type="button" className="demo-row demo-row-button" data-testid="button-demo-admin" onClick={() => fillDemo(DEMO_USERS[0])}>
              <span><strong>Admin</strong> · admin@fisio.com</span>
              <span className="demo-password">Admin@123</span>
            </button>
            <button type="button" className="demo-row demo-row-button" data-testid="button-demo-fisio" onClick={() => fillDemo(DEMO_USERS[1])}>
              <span><strong>Fisio</strong> · fisio@fisio.com</span>
              <span className="demo-password">Fisio@123</span>
            </button>
          </div>
          <p className="login-footer">Ambiente acadêmico · Projeto Integrador</p>
        </div>
      </section>
    </main>
  );
}

function Sidebar({ user, onLogout }: { user: User; onLogout: () => void }) {
  const [, setLocation] = useLocation();
  const isAdmin = user.tipo_usuario === 'admin';
  const home = dashboardPath(user.tipo_usuario);
  const logout = () => {
    onLogout();
    setLocation('/');
  };

  return (
    <aside className="fb-sidebar" aria-label="Navegação principal">
      <Link href={home} className="sidebar-brand" data-testid="link-sidebar-brand" aria-label="FisioBase, início">
        <Brand small />
        <span>Fisio<em>Base</em></span>
      </Link>
      <div className="sidebar-user" data-testid="card-current-user">
        <span className={`fb-avatar ${isAdmin ? 'fb-avatar--admin' : ''}`} aria-hidden="true">{initials(user.nome)}</span>
        <div>
          <strong data-testid="text-current-user">{user.nome}</strong>
          <small>{isAdmin ? 'Administrador' : 'Fisioterapeuta'}</small>
        </div>
      </div>
      <nav className="fb-nav">
        <p className="nav-label">{isAdmin ? 'Visão geral' : 'Minha rotina'}</p>
        <Link href={home} className="nav-item nav-item--active" data-testid="link-dashboard">
          <LayoutDashboard size={16} className="nav-icon" aria-hidden="true" />
          {isAdmin ? 'Dashboard' : 'Minha área'}
        </Link>
        <p className="nav-label">{isAdmin ? 'Gestão' : 'Atendimento'}</p>
        {(isAdmin ? [
          { label: 'Profissionais', icon: Users },
          { label: 'Pacientes', icon: ClipboardList },
          { label: 'Relatórios', icon: Activity },
        ] : [
          { label: 'Minha agenda', icon: CalendarDays },
          { label: 'Meus pacientes', icon: Users },
        ]).map(({ label, icon: Icon }) => (
          <button type="button" className="nav-item" disabled key={label} data-testid={`button-upcoming-${label.toLowerCase().replaceAll(' ', '-')}`}>
            <Icon size={16} className="nav-icon" aria-hidden="true" />
            {label}
            <span className="nav-soon">Em breve</span>
          </button>
        ))}
      </nav>
      <div className="sidebar-bottom">
        <div className="sidebar-status" data-testid="status-system">
          <span className="status-dot" aria-hidden="true" />
          <span>Sistema operacional</span>
        </div>
        <button type="button" className="nav-item nav-item--logout" data-testid="button-logout" onClick={logout}>
          <LogOut size={16} className="nav-icon" aria-hidden="true" />
          Sair da conta
        </button>
      </div>
    </aside>
  );
}

function DashboardLayout({ user, onLogout, children }: { user: User; onLogout: () => void; children: ReactNode }) {
  return (
    <div className="app-shell fb-page fb-noise">
      <Sidebar user={user} onLogout={onLogout} />
      <main className="main-content" id="conteudo">{children}</main>
    </div>
  );
}

function DashboardTop({ user, label, title, context }: { user: User; label: string; title: string; context: string }) {
  return (
    <>
      <header className="topbar fb-reveal">
        <div>
          <p className="breadcrumb">{label} <span>/</span> {title}</p>
          <h1 className="fb-display">Olá, {firstName(user.nome)}.</h1>
        </div>
        <div className="topbar-date" data-testid="text-dashboard-context">
          <ShieldCheck size={15} className="date-icon" aria-hidden="true" />
          <span>{context}</span>
        </div>
      </header>
      <div className="demo-banner fb-reveal fb-reveal-delay-1" role="status" data-testid="status-dashboard-demo">
        <Activity size={14} aria-hidden="true" />
        <span>Modo demonstração · dados locais para apresentação do produto</span>
      </div>
    </>
  );
}

function WelcomeBanner({ professional }: { professional?: boolean }) {
  return (
    <section className={`welcome-banner ${professional ? 'welcome-banner--green' : ''} fb-reveal fb-reveal-delay-1`} aria-label="Resumo do sistema">
      <div>
        <p className="fb-kicker">{professional ? 'Seu espaço de trabalho' : 'Painel do administrador'}</p>
        <h2 className="fb-display">{professional ? 'Seu cuidado, no seu ritmo.' : 'O cuidado começa pela organização.'}</h2>
        <p>{professional ? 'Acompanhe sua agenda e seus pacientes em um só lugar.' : 'Tenha uma visão clara da operação do consultório em um só lugar.'}</p>
      </div>
      <span className="welcome-art" aria-hidden="true"><span /><span /><span /></span>
    </section>
  );
}

function StatCard({ label, value, caption, icon: Icon, tone }: { label: string; value: string; caption: string; icon: typeof Activity; tone: 'blue' | 'yellow' | 'green' }) {
  return (
    <article className="stat-card fb-reveal fb-reveal-delay-2" data-testid={`card-stat-${label.toLowerCase().replaceAll(' ', '-')}`}>
      <div className="stat-card__top">
        <span className="stat-label">{label}</span>
        <span className={`stat-icon stat-icon--${tone}`}><Icon size={15} aria-hidden="true" /></span>
      </div>
      <strong className="stat-value" data-testid={`value-stat-${label.toLowerCase().replaceAll(' ', '-')}`}>{value}</strong>
      <span className="stat-caption">{caption}</span>
    </article>
  );
}

function AdminDashboard({ user, onLogout }: { user: User; onLogout: () => void }) {
  return (
    <DashboardLayout user={user} onLogout={onLogout}>
      <DashboardTop user={user} label="Visão geral" title="Dashboard" context="Visão administrativa" />
      <WelcomeBanner />
      <section className="stats-grid" aria-label="Resumo dos usuários">
        <StatCard label="Usuários ativos" value={String(DEMO_USERS.length)} caption="contas cadastradas" icon={Users} tone="blue" />
        <StatCard label="Administradores" value="1" caption="com acesso total" icon={ShieldCheck} tone="yellow" />
        <StatCard label="Fisioterapeutas" value="1" caption="profissional da equipe" icon={Stethoscope} tone="green" />
      </section>
      <section className="content-grid">
        <article className="panel fb-reveal fb-reveal-delay-3">
          <div className="panel-heading">
            <div><p className="eyebrow-muted">Controle de acesso</p><h2>Usuários do sistema</h2></div>
            <span className="panel-count" data-testid="text-user-count">{DEMO_USERS.length} registros</span>
          </div>
          <div className="table-wrap">
            <table>
              <caption className="sr-only">Lista de usuários cadastrados no sistema</caption>
              <thead><tr><th scope="col">Profissional</th><th scope="col">E-mail</th><th scope="col">Perfil</th><th scope="col">Status</th></tr></thead>
              <tbody>
                {DEMO_USERS.map((demoUser) => (
                  <tr key={demoUser.id} data-testid={`row-user-${demoUser.id}`}>
                    <td><div className="table-person"><span className={`fb-avatar avatar-table ${demoUser.tipo_usuario === 'admin' ? 'fb-avatar--admin' : ''}`} aria-hidden="true">{initials(demoUser.nome)}</span><strong>{demoUser.nome}</strong></div></td>
                    <td className="muted-cell">{demoUser.email}</td>
                    <td><span className={`role-badge role-badge--${demoUser.tipo_usuario}`}>{demoUser.tipo_usuario === 'admin' ? 'Administrador' : 'Fisioterapeuta'}</span></td>
                    <td><span className="status-badge"><span className="status-dot" aria-hidden="true" />Ativo</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>
        <aside className="panel fb-reveal fb-reveal-delay-3">
          <div className="panel-heading"><div><p className="eyebrow-muted">Próximos passos</p><h2>Base inicial</h2></div></div>
          <div className="roadmap">
            <div className="roadmap-item roadmap-item--done"><span className="roadmap-marker"><Check size={13} aria-hidden="true" /></span><div><strong>Autenticação</strong><span>Concluído</span></div></div>
            <div className="roadmap-item roadmap-item--current"><span className="roadmap-marker">2</span><div><strong>Pacientes</strong><span>Próxima etapa</span></div></div>
            <div className="roadmap-item"><span className="roadmap-marker">3</span><div><strong>Agenda</strong><span>Planejado</span></div></div>
          </div>
          <div className="panel-note">A estrutura está pronta para receber os próximos módulos do projeto.</div>
        </aside>
      </section>
    </DashboardLayout>
  );
}

function PhysiotherapistDashboard({ user, onLogout }: { user: User; onLogout: () => void }) {
  return (
    <DashboardLayout user={user} onLogout={onLogout}>
      <DashboardTop user={user} label="Minha rotina" title="Minha área" context="Área do profissional" />
      <WelcomeBanner professional />
      <section className="stats-grid" aria-label="Resumo da rotina">
        <StatCard label="Atendimentos hoje" value="—" caption="agenda em preparação" icon={CalendarDays} tone="blue" />
        <StatCard label="Meus pacientes" value="—" caption="cadastro na próxima etapa" icon={Users} tone="green" />
        <StatCard label="Presenças do mês" value="—" caption="registro em breve" icon={Check} tone="yellow" />
      </section>
      <section className="content-grid content-grid--single">
        <article className="panel fb-reveal fb-reveal-delay-3">
          <div className="panel-heading">
            <div><p className="eyebrow-muted">Seu próximo módulo</p><h2>Área pronta para evoluir</h2></div>
            <span className="role-badge role-badge--fisioterapeuta">Acesso restrito</span>
          </div>
          <div className="empty-state" data-testid="empty-professional-modules">
            <div className="empty-state-icon" aria-hidden="true"><Activity size={23} /></div>
            <h3>Agenda e pacientes entram na próxima etapa</h3>
            <p>Seu perfil já está protegido. Quando os módulos clínicos forem adicionados, você verá somente a sua agenda e os seus próprios pacientes aqui.</p>
          </div>
        </article>
      </section>
    </DashboardLayout>
  );
}

function ForbiddenPage({ user, target }: { user: User | null; target?: string }) {
  const [, setLocation] = useLocation();
  const destination = user ? dashboardPath(user.tipo_usuario) : '/';
  return (
    <main className="forbidden-page fb-noise">
      <section className="forbidden-card fb-reveal" aria-labelledby="forbidden-title">
        <div className="forbidden-icon" aria-hidden="true"><LockKeyhole size={24} /></div>
        <p className="fb-kicker" style={{ color: 'hsl(var(--destructive))' }}>Acesso não permitido</p>
        <h1 id="forbidden-title" className="fb-display">Este espaço não é seu.</h1>
        <p>{user ? `Seu perfil não tem permissão para acessar ${target ?? 'esta área'}. O FisioBase mantém cada rotina no nível certo de acesso.` : 'Entre no sistema para continuar com segurança.'}</p>
        <button type="button" className="fb-button fb-button--primary" data-testid="button-forbidden-return" onClick={() => setLocation(destination)}>
          {user ? 'Voltar para minha área' : 'Ir para o acesso'}
          <ArrowRight size={16} aria-hidden="true" />
        </button>
      </section>
    </main>
  );
}

function PageLoading() {
  return <div className="fb-page" aria-label="Carregando" data-testid="status-page-loading" />;
}

function Router() {
  const [location, setLocation] = useLocation();
  const [user, setUser] = useState<User | null>(() => {
    const stored = window.localStorage.getItem('fisiobase-demo-user');
    if (!stored) return null;
    try { return JSON.parse(stored) as User; } catch { return null; }
  });

  useEffect(() => {
    if (location === '/' && user) setLocation(dashboardPath(user.tipo_usuario));
  }, [location, setLocation, user]);

  const login = (nextUser: User) => {
    setUser(nextUser);
    window.localStorage.setItem('fisiobase-demo-user', JSON.stringify(nextUser));
  };
  const logout = () => {
    setUser(null);
    window.localStorage.removeItem('fisiobase-demo-user');
  };

  return (
    <ErrorBoundary resetKey={location}>
      <Switch>
        <Route path="/" component={() => user ? <PageLoading /> : <LoginPage onLogin={login} />} />
        <Route path="/login" component={() => <LoginPage onLogin={login} />} />
        <Route path="/dashboard/admin" component={() => user ? (user.tipo_usuario === 'admin' ? <AdminDashboard user={user} onLogout={logout} /> : <ForbiddenPage user={user} target="o painel administrativo" />) : <ForbiddenPage user={null} target="o painel administrativo" />} />
        <Route path="/dashboard/fisioterapeuta" component={() => user ? (user.tipo_usuario === 'fisioterapeuta' ? <PhysiotherapistDashboard user={user} onLogout={logout} /> : <ForbiddenPage user={user} target="a área do fisioterapeuta" />) : <ForbiddenPage user={null} target="a área do fisioterapeuta" />} />
        <Route path="/forbidden" component={() => <ForbiddenPage user={user} />} />
        <Route component={NotFound} />
      </Switch>
    </ErrorBoundary>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <WouterRouter base={import.meta.env.BASE_URL.replace(/\/$/, '')}>
          <Router />
        </WouterRouter>
        <Toaster />
      </TooltipProvider>
    </QueryClientProvider>
  );
}

export default App;