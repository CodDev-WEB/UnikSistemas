import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity, ArrowDownToLine, ArrowRight, Bell, Building2, Check, ChevronDown,
  CircleHelp, Clock3, Download, FileSpreadsheet, FileText, LayoutDashboard, LockKeyhole, LogOut, Plus, Mail, CheckCheck,
  RefreshCw, Search, Settings2, ShieldCheck, Users, UserPlus, UserCog, ClipboardList, CalendarDays, X,
} from "lucide-react";

type Tenant = { id: string; name: string; slug: string; status: string };
type User = { id: string; tenant_id: string; email: string; full_name: string; role: string; is_active: boolean };
type Client = {
  id: string; legal_name: string; trade_name: string | null; tax_id: string | null;
  email: string | null; phone: string | null; status: "active" | "archived";
  created_at: string | null;
};
type Me = { user: User; tenant: Tenant };
type ImportRow = {
  row_number: number; legal_name: string | null; trade_name: string | null;
  tax_id: string | null; email: string | null; phone: string | null;
  status: string | null; errors: string[];
};
type ImportStatus = "ready" | "invalid" | "confirmed" | "discarded";
type ImportBatch = {
  id: string; filename: string; status: ImportStatus;
  total_rows: number; imported_count: number; rows: ImportRow[];
  created_at: string | null; confirmed_at: string | null;
};
type ImportHistoryEntry = {
  id: string; filename: string; status: ImportStatus; total_rows: number;
  imported_count: number; created_by_name: string | null;
  created_at: string | null; confirmed_at: string | null;
};

function importStatusLabel(status: ImportStatus) {
  return {
    ready: "Pendente de confirmação",
    invalid: "Com pendências",
    confirmed: "Importada",
    discarded: "Descartada",
  }[status];
}

function importStatusClass(status: ImportStatus) {
  if (status === "confirmed") return "status-active";
  if (status === "ready") return "status-pending";
  return "status-archived";
}
type ClientTask = {
  id: string; client_id: string; client_name: string; title: string; description: string | null;
  kind: "document" | "follow_up" | "routine"; priority: "low" | "normal" | "high";
  status: "open" | "received" | "completed" | "cancelled"; due_date: string | null;
  assigned_to_user_id: string | null; assigned_to_name: string | null;
  created_by_user_id: string | null; created_by_name: string | null;
  completed_at: string | null; created_at: string | null; updated_at: string | null;
};
type TaskStatus = ClientTask["status"];
type TaskForm = {
  client_id: string; title: string; description: string; kind: ClientTask["kind"];
  priority: ClientTask["priority"]; due_date: string; assigned_to_user_id: string;
};
const taskStatusLabels: Record<TaskStatus, string> = {
  open: "Pendente", received: "Recebido", completed: "Concluído", cancelled: "Cancelado",
};
const taskKindLabels: Record<ClientTask["kind"], string> = {
  document: "Documento", follow_up: "Acompanhamento", routine: "Rotina interna",
};
const taskPriorityLabels: Record<ClientTask["priority"], string> = {
  low: "Baixa", normal: "Normal", high: "Alta",
};
type TokenResponse = { access_token: string; token_type: string; expires_in: number };

type NotificationEventType = "document_received" | "task_assigned" | "task_due";
type NotificationEmailStatus = {
  enabled: boolean; configured: boolean; pending: number; failed: number; note: string;
};
type NotificationRecord = {
  id: string; event_type: NotificationEventType; title: string; message: string;
  entity_type: string; entity_id: string; action_url: string | null; is_read: boolean;
  email_status: "pending" | "sent" | "failed"; email_attempts: number;
  email_sent_at: string | null; created_at: string | null;
};
type DueReminderResult = {
  created: number; due_items_checked: number; email_enabled: boolean;
  queued_email_count: number; failed_email_count: number;
};
const notificationEmailLabels: Record<NotificationRecord["email_status"], string> = {
  pending: "Na fila de e-mail", sent: "E-mail enviado", failed: "Falha no e-mail",
};
function notificationKindLabel(kind: NotificationEventType) {
  if (kind === "document_received") return "Documento recebido";
  if (kind === "task_assigned") return "Nova atribuição";
  return "Prazo de pendência";
}


type ClientDocument = {
  id: string; task_id: string; task_title: string; client_name: string;
  original_filename: string; content_type: string; file_size: number; sha256: string;
  review_status: "pending" | "accepted" | "rejected"; review_note: string | null;
  reviewed_by_name: string | null; reviewed_at: string | null; created_at: string | null;
};
type DocumentUploadInfo = {
  title: string; description: string | null; expires_at: string;
  remaining_uploads: number; max_file_size_bytes: number; allowed_extensions: string[];
};
type UploadLinkResponse = { id: string; public_path: string; expires_at: string; max_uploads: number };
type ActiveUploadLink = { id: string; url: string; expires_at: string };

const documentReviewLabels: Record<ClientDocument["review_status"], string> = {
  pending: "Aguardando conferência", accepted: "Conferido", rejected: "Precisa de correção",
};
function fileSizeLabel(size: number) {
  if (size < 1024 * 1024) return Math.max(1, Math.round(size / 1024)) + " KB";
  return (size / (1024 * 1024)).toFixed(1).replace(".", ",") + " MB";
}


async function api<T>(path: string, init: RequestInit = {}, token?: string): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(path, { ...init, headers });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = typeof payload.detail === "string" ? payload.detail : "Não foi possível concluir a operação.";
    throw new Error(message);
  }
  return payload as T;
}


function PublicDocumentUploadPage({ token }: { token: string }) {
  const [info, setInfo] = useState<DocumentUploadInfo | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    let active = true;
    setLoading(true);
    api<DocumentUploadInfo>("/api/v1/public/document-upload/" + encodeURIComponent(token))
      .then(result => { if (active) setInfo(result); })
      .catch(err => { if (active) setError(err instanceof Error ? err.message : "Este link não está disponível."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [token]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file || !info) return;
    if (file.size > info.max_file_size_bytes) {
      setError("O arquivo ultrapassa o limite de 10 MiB.");
      return;
    }
    setBusy(true);
    setError("");
    setSuccess("");
    try {
      const form = new FormData();
      form.append("file", file);
      await api<{ id: string; filename: string }>("/api/v1/public/document-upload/" + encodeURIComponent(token) + "/files", {
        method: "POST", body: form,
      });
      setInfo(current => current ? { ...current, remaining_uploads: Math.max(0, current.remaining_uploads - 1) } : current);
      setFile(null);
      setSuccess("Arquivo enviado com sucesso. O escritório já pode conferir o documento.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível enviar o arquivo.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="login-screen document-upload-screen">
      <section className="login-panel public-upload-panel">
        <div className="brand-lockup">
          <div className="brand-mark"><Building2 size={22} strokeWidth={2.3}/></div>
          <div><span className="brand-name">unik<span>sistemas</span></span><span className="brand-subtitle">ENVIO SEGURO DE DOCUMENTOS</span></div>
        </div>
        {loading ? (
          <div className="loading-state"><div className="spinner"/><span>Validando link...</span></div>
        ) : error && !info ? (
          <div className="public-upload-content"><div className="eyebrow">LINK INDISPONÍVEL</div><h1>Este endereço não está mais ativo.</h1><p>Peça ao escritório contábil para gerar um novo link de envio.</p><div className="alert alert-error" role="alert">{error}</div></div>
        ) : info ? (
          <div className="public-upload-content">
            <div className="eyebrow"><span className="eyebrow-dot"/> SOLICITAÇÃO DE DOCUMENTO</div>
            <h1>{info.title}</h1>
            <p>{info.description || "Selecione o documento solicitado e envie para conferência pelo escritório."}</p>
            <div className="public-upload-rules">
              <div><strong>Prazo do link</strong><span>{formatDateTime(info.expires_at)}</span></div>
              <div><strong>Envios restantes</strong><span>{info.remaining_uploads}</span></div>
              <div><strong>Tamanho máximo</strong><span>10 MiB por arquivo</span></div>
            </div>
            {info.remaining_uploads > 0 ? (
              <form className="public-upload-form" onSubmit={submit}>
                <label className="public-upload-drop" htmlFor="public-document-file">
                  <FileText size={24}/>
                  <strong>{file ? file.name : "Escolher arquivo"}</strong>
                  <small>{file ? fileSizeLabel(file.size) + " · pronto para enviar" : "PDF, PNG, JPG, CSV, XLSX ou DOCX"}</small>
                  <input id="public-document-file" type="file" accept=".pdf,.png,.jpg,.jpeg,.csv,.xlsx,.docx" onChange={event => setFile(event.target.files?.[0] ?? null)} required/>
                </label>
                {error && <div className="alert alert-error" role="alert">{error}</div>}
                {success && <div className="alert alert-success" role="status">{success}</div>}
                <button className="button button-primary public-upload-submit" type="submit" disabled={!file || busy}>
                  {busy ? "Enviando arquivo..." : "Enviar documento"} {!busy && <ArrowDownToLine size={16}/>}
                </button>
              </form>
            ) : (
              <div className="alert alert-success" role="status">Este link atingiu o limite de envios. O escritório poderá emitir outro, se necessário.</div>
            )}
            <p className="public-upload-privacy"><LockKeyhole size={14}/> O arquivo será disponibilizado apenas à equipe autenticada do escritório. Não envie senhas nem documentos que não foram solicitados.</p>
          </div>
        ) : null}
        <div className="login-footer">UNIKSISTEMAS <span>·</span> ENVIO DE ARQUIVOS</div>
      </section>
    </main>
  );
}

function initials(name: string) {
  return name.trim().split(/\s+/).slice(0, 2).map(part => part[0]?.toUpperCase() ?? "").join("");
}

function formatDate(value: string | null) {
  if (!value) return "—";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? "—" : new Intl.DateTimeFormat("pt-BR").format(parsed);
}

function formatDateTime(value: string | null) {
  if (!value) return "—";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime())
    ? "—"
    : new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" }).format(parsed);
}

export default function App() {
  const publicUploadToken = window.location.pathname.match(/^\/document-upload\/([^/]+)\/?$/)?.[1] ?? "";
  const [token, setToken] = useState(() => sessionStorage.getItem("unik_access_token") ?? "");
  const [me, setMe] = useState<Me | null>(null);
  const [clients, setClients] = useState<Client[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [currentPage, setCurrentPage] = useState<"dashboard" | "clients" | "users" | "imports" | "tasks" | "notifications">(() => {
    if (window.location.pathname === "/tasks") return "tasks";
    if (window.location.pathname === "/notifications") return "notifications";
    return "dashboard";
  });
  const [tasks, setTasks] = useState<ClientTask[]>([]);
  const [notifications, setNotifications] = useState<NotificationRecord[]>([]);
  const [notificationEmailStatus, setNotificationEmailStatus] = useState<NotificationEmailStatus | null>(null);
  const [notificationsLoading, setNotificationsLoading] = useState(false);
  const [notificationActionBusy, setNotificationActionBusy] = useState<string | null>(null);
  const [documents, setDocuments] = useState<ClientDocument[]>([]);
  const [taskUploadLinks, setTaskUploadLinks] = useState<Record<string, ActiveUploadLink>>({});
  const [taskLinkBusy, setTaskLinkBusy] = useState<string | null>(null);
  const [taskFilter, setTaskFilter] = useState<"all" | TaskStatus>("open");
  const [taskClientFilter, setTaskClientFilter] = useState("all");
  const [taskSearch, setTaskSearch] = useState("");
  const [showTaskForm, setShowTaskForm] = useState(false);
  const [tasksLoading, setTasksLoading] = useState(false);
  const [taskBusy, setTaskBusy] = useState(false);
  const [taskForm, setTaskForm] = useState<TaskForm>({
    client_id: "", title: "", description: "", kind: "document",
    priority: "normal", due_date: "", assigned_to_user_id: "",
  });
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importBatch, setImportBatch] = useState<ImportBatch | null>(null);
  const [importHistory, setImportHistory] = useState<ImportHistoryEntry[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [templateBusy, setTemplateBusy] = useState<"csv" | "xlsx" | null>(null);
  const [loginForm, setLoginForm] = useState({ tenant_slug: "", email: "", password: "" });
  const [clientForm, setClientForm] = useState({ legal_name: "", trade_name: "", tax_id: "", email: "", phone: "" });
  const [userForm, setUserForm] = useState({ full_name: "", email: "", password: "", role: "accountant" });
  const [search, setSearch] = useState("");
  const [clientFilter, setClientFilter] = useState<"all" | "active" | "archived">("all");
  const [showCreate, setShowCreate] = useState(false);
  const [loginBusy, setLoginBusy] = useState(false);
  const [clientBusy, setClientBusy] = useState(false);
  const [userBusy, setUserBusy] = useState(false);
  const [importBusy, setImportBusy] = useState(false);
  const [confirmImportBusy, setConfirmImportBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const loadImportHistory = useCallback(async (activeToken: string) => {
    setHistoryLoading(true);
    try {
      const history = await api<ImportHistoryEntry[]>("/api/v1/imports/clients?limit=50", {}, activeToken);
      setImportHistory(history);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível carregar o histórico.");
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  const loadClientTasks = useCallback(async (activeToken: string) => {
    setTasksLoading(true);
    try {
      const [rows, files] = await Promise.all([
        api<ClientTask[]>("/api/v1/tasks?limit=100", {}, activeToken),
        api<ClientDocument[]>("/api/v1/documents?limit=100", {}, activeToken),
      ]);
      setTasks(rows);
      setDocuments(files);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível carregar as pendências.");
    } finally {
      setTasksLoading(false);
    }
  }, []);

  const loadNotifications = useCallback(async (activeToken: string, canManageEmail: boolean) => {
    setNotificationsLoading(true);
    try {
      const rows = await api<NotificationRecord[]>("/api/v1/notifications?limit=100", {}, activeToken);
      setNotifications(rows);
      if (canManageEmail) {
        try {
          const status = await api<NotificationEmailStatus>("/api/v1/notifications/email-status", {}, activeToken);
          setNotificationEmailStatus(status);
        } catch {
          setNotificationEmailStatus(null);
        }
      } else {
        setNotificationEmailStatus(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível carregar as notificações.");
    } finally {
      setNotificationsLoading(false);
    }
  }, []);


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
      await loadNotifications(activeToken, ["owner", "admin"].includes(profile.user.role));
      setError("");
    } catch (err) {
      sessionStorage.removeItem("unik_access_token");
      setToken("");
      setMe(null);
      setClients([]);
      setUsers([]);
      setImportFile(null);
      setImportBatch(null);
      setImportHistory([]);
      setTasks([]);
      setNotifications([]);
      setNotificationEmailStatus(null);
      setDocuments([]);
      setTaskUploadLinks({});
      setShowTaskForm(false);
      setTaskForm({
    client_id: "", title: "", description: "", kind: "document",
    priority: "normal", due_date: "", assigned_to_user_id: "",
  });
      setTaskClientFilter("all");
      setTaskSearch("");
      setCurrentPage("dashboard");
      setError(err instanceof Error ? err.message : "Sua sessão não está disponível.");
    } finally {
      setLoading(false);
    }
  }, [loadNotifications]);

  useEffect(() => {
    if (publicUploadToken) {
      setLoading(false);
      return;
    }
    if (token) {
      void loadWorkspace(token);
    } else {
      setLoading(false);
      setMe(null);
      setClients([]);
      setUsers([]);
      setImportFile(null);
      setImportBatch(null);
      setImportHistory([]);
      setTasks([]);
      setNotifications([]);
      setNotificationEmailStatus(null);
      setShowTaskForm(false);
      setTaskForm({
    client_id: "", title: "", description: "", kind: "document",
    priority: "normal", due_date: "", assigned_to_user_id: "",
  });
      setTaskClientFilter("all");
      setTaskSearch("");
      setCurrentPage("dashboard");
    }
  }, [token, loadWorkspace, publicUploadToken]);

  useEffect(() => {
    if (token && me && currentPage === "imports") {
      void loadImportHistory(token);
    }
  }, [token, me, currentPage, loadImportHistory]);

  useEffect(() => {
    if (token && me && currentPage === "tasks") {
      void loadClientTasks(token);
    }
  }, [token, me, currentPage, loadClientTasks]);

  const filteredTasks = useMemo(() => {
    const query = taskSearch.trim().toLocaleLowerCase("pt-BR");
    return tasks.filter(task => {
      const matchesStatus = taskFilter === "all" || task.status === taskFilter;
      const matchesClient = taskClientFilter === "all" || task.client_id === taskClientFilter;
      const haystack = [task.title, task.description ?? "", task.client_name, task.assigned_to_name ?? ""]
        .join(" ").toLocaleLowerCase("pt-BR");
      return matchesStatus && matchesClient && (!query || haystack.includes(query));
    });
  }, [tasks, taskFilter, taskClientFilter, taskSearch]);

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



  async function handleCreateTask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token || !taskForm.client_id) return;
    setTaskBusy(true);
    setError("");
    setSuccess("");
    try {
      const created = await api<ClientTask>("/api/v1/tasks", {
        method: "POST",
        body: JSON.stringify({
          client_id: taskForm.client_id,
          title: taskForm.title.trim(),
          description: taskForm.description.trim() || null,
          kind: taskForm.kind,
          priority: taskForm.priority,
          due_date: taskForm.due_date || null,
          assigned_to_user_id: taskForm.assigned_to_user_id || null,
        }),
      }, token);
      setTasks(previous => [created, ...previous]);
      setTaskForm({
        client_id: "", title: "", description: "", kind: "document",
        priority: "normal", due_date: "", assigned_to_user_id: "",
      });
      setShowTaskForm(false);
      setSuccess("Pendência registrada para o cliente.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível criar a pendência.");
    } finally {
      setTaskBusy(false);
    }
  }

  async function handleUpdateTask(taskId: string, patch: { status?: TaskStatus; due_date?: string | null; assigned_to_user_id?: string | null }) {
    if (!token) return;
    setTaskBusy(true);
    setError("");
    setSuccess("");
    try {
      const updated = await api<ClientTask>(`/api/v1/tasks/${taskId}`, {
        method: "PATCH",
        body: JSON.stringify(patch),
      }, token);
      setTasks(previous => previous.map(task => task.id === updated.id ? updated : task));
      setSuccess(`Pendência atualizada: ${taskStatusLabels[updated.status]}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível atualizar a pendência.");
    } finally {
      setTaskBusy(false);
    }
  }


  async function handleCreateUploadLink(taskId: string) {
    if (!token) return;
    setTaskLinkBusy(taskId);
    setError("");
    setSuccess("");
    try {
      const result = await api<UploadLinkResponse>("/api/v1/tasks/" + taskId + "/upload-link", { method: "POST" }, token);
      setTaskUploadLinks(previous => ({
        ...previous,
        [taskId]: { id: result.id, url: window.location.origin + result.public_path, expires_at: result.expires_at },
      }));
      setSuccess("Link temporário gerado. Copie e envie ao cliente por um canal seguro.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível gerar o link de envio.");
    } finally {
      setTaskLinkBusy(null);
    }
  }

  async function handleCopyUploadLink(url: string) {
    try {
      await navigator.clipboard.writeText(url);
      setSuccess("Link copiado. Envie-o ao cliente por um canal seguro.");
    } catch {
      setSuccess("Não foi possível copiar automaticamente. Selecione e copie o link exibido.");
    }
  }

  async function handleRevokeUploadLink(taskId: string) {
    if (!token || !taskUploadLinks[taskId]) return;
    setTaskLinkBusy(taskId);
    try {
      await api<unknown>("/api/v1/tasks/" + taskId + "/upload-links/" + taskUploadLinks[taskId].id + "/revoke", { method: "POST" }, token);
      setTaskUploadLinks(previous => {
        const next = { ...previous };
        delete next[taskId];
        return next;
      });
      setSuccess("Link de envio revogado.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível revogar o link.");
    } finally {
      setTaskLinkBusy(null);
    }
  }

  async function handleReviewDocument(documentId: string, reviewStatus: "accepted" | "rejected") {
    if (!token) return;
    setTaskBusy(true);
    setError("");
    try {
      const updated = await api<ClientDocument>("/api/v1/documents/" + documentId, {
        method: "PATCH",
        body: JSON.stringify({ review_status: reviewStatus }),
      }, token);
      setDocuments(previous => previous.map(item => item.id === updated.id ? updated : item));
      setSuccess(reviewStatus === "accepted" ? "Documento conferido." : "Documento marcado para correção.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível registrar a conferência.");
    } finally {
      setTaskBusy(false);
    }
  }

  async function handleDownloadDocument(documentId: string, filename: string) {
    if (!token) return;
    try {
      const response = await fetch("/api/v1/documents/" + documentId + "/download", {
        headers: { Authorization: "Bearer " + token },
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(typeof payload.detail === "string" ? payload.detail : "Não foi possível baixar o arquivo.");
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = filename;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível baixar o arquivo.");
    }
  }


  async function handleMarkNotificationRead(notificationId: string) {
    if (!token) return;
    setNotificationActionBusy(notificationId);
    try {
      const updated = await api<NotificationRecord>("/api/v1/notifications/" + notificationId + "/read", {
        method: "PATCH",
      }, token);
      setNotifications(previous => previous.map(item => item.id === updated.id ? updated : item));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível marcar a notificação como lida.");
    } finally {
      setNotificationActionBusy(null);
    }
  }

  async function handleMarkAllNotificationsRead() {
    if (!token) return;
    setNotificationActionBusy("all");
    try {
      await api<{ marked_read: number }>("/api/v1/notifications/read-all", { method: "POST" }, token);
      setNotifications(previous => previous.map(item => ({ ...item, is_read: true })));
      setSuccess("Todas as notificações foram marcadas como lidas.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível atualizar as notificações.");
    } finally {
      setNotificationActionBusy(null);
    }
  }

  async function handleProcessDueReminders() {
    if (!token) return;
    setNotificationActionBusy("due-reminders");
    setError("");
    try {
      const result = await api<DueReminderResult>("/api/v1/notifications/process-due-reminders", {
        method: "POST",
      }, token);
      await loadNotifications(token, ["owner", "admin"].includes(me?.user.role ?? ""));
      setSuccess(
        result.created
          ? `${result.created} alerta(s) de prazo criado(s); ${result.due_items_checked} pendência(s) verificadas.`
          : `Verificação concluída: ${result.due_items_checked} pendência(s), sem novos alertas hoje.`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível verificar os prazos.");
    } finally {
      setNotificationActionBusy(null);
    }
  }

  async function handleRetryNotificationEmail(notificationId: string) {
    if (!token) return;
    setNotificationActionBusy(notificationId);
    setError("");
    try {
      await api<{ queued: boolean }>("/api/v1/notifications/" + notificationId + "/retry-email", {
        method: "POST",
      }, token);
      await loadNotifications(token, ["owner", "admin"].includes(me?.user.role ?? ""));
      setSuccess("E-mail recolocado na fila de envio.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível reenfileirar o e-mail.");
    } finally {
      setNotificationActionBusy(null);
    }
  }

  async function handleOpenNotification(item: NotificationRecord) {
    if (!item.is_read) await handleMarkNotificationRead(item.id);
    if (item.action_url === "/tasks") setCurrentPage("tasks");
  }

  async function handleDownloadTemplate(format: "csv" | "xlsx") {
    if (!token) return;
    setTemplateBusy(format);
    setError("");
    try {
      const response = await fetch(`/api/v1/imports/client-template.${format}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(typeof payload.detail === "string" ? payload.detail : "Não foi possível baixar o modelo.");
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `unik-modelo-clientes.${format}`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível baixar o modelo.");
    } finally {
      setTemplateBusy(null);
    }
  }

  async function handleOpenImportHistory(batchId: string) {
    if (!token) return;
    setError("");
    setSuccess("");
    try {
      const batch = await api<ImportBatch>(`/api/v1/imports/clients/${batchId}`, {}, token);
      setImportBatch(batch);
      setImportFile(null);
      setSuccess(`Detalhes do lote: ${batch.filename}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível abrir a importação.");
    }
  }

  async function handlePreviewImport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token || !importFile) return;
    setImportBusy(true);
    setError("");
    setSuccess("");
    try {
      if (importBatch && importBatch.status !== "confirmed") {
        await api<unknown>(`/api/v1/imports/clients/${importBatch.id}`, { method: "DELETE" }, token);
      }
      setImportBatch(null);
      const body = new FormData();
      body.append("file", importFile);
      const preview = await api<ImportBatch>("/api/v1/imports/clients/preview", {
        method: "POST",
        body,
      }, token);
      setImportBatch(preview);
      await loadImportHistory(token);
      setSuccess(preview.status === "ready"
        ? "Prévia validada. Confira os dados e confirme para gravar os clientes."
        : "A prévia encontrou pendências. Corrija o arquivo e envie novamente.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível validar a planilha.");
    } finally {
      setImportBusy(false);
    }
  }

  async function handleConfirmImport() {
    if (!token || !importBatch || importBatch.status !== "ready") return;
    setConfirmImportBusy(true);
    setError("");
    setSuccess("");
    try {
      const confirmed = await api<ImportBatch>(
        `/api/v1/imports/clients/${importBatch.id}/confirm`,
        { method: "POST" },
        token,
      );
      setImportBatch(confirmed);
      const updatedClients = await api<Client[]>("/api/v1/clients?limit=100", {}, token);
      setClients(updatedClients);
      await loadImportHistory(token);
      setSuccess(`${confirmed.imported_count} cliente(s) importado(s) com sucesso.`);
    } catch (err) {
      try {
        const latest = await api<ImportBatch>(`/api/v1/imports/clients/${importBatch.id}`, {}, token);
        setImportBatch(latest);
      } catch {
        // Keep the original error when the status endpoint is also unavailable.
      }
      await loadImportHistory(token);
      setError(err instanceof Error ? err.message : "Não foi possível confirmar a importação.");
    } finally {
      setConfirmImportBusy(false);
    }
  }

  async function handleDiscardImport() {
    if (!token || !importBatch || importBatch.status === "confirmed") return;
    setImportBusy(true);
    setError("");
    setSuccess("");
    try {
      await api<unknown>(`/api/v1/imports/clients/${importBatch.id}`, { method: "DELETE" }, token);
      setImportBatch(null);
      setImportFile(null);
      await loadImportHistory(token);
      setSuccess("Prévia descartada. O registro foi mantido no histórico.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível descartar a prévia.");
    } finally {
      setImportBusy(false);
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
    setImportFile(null);
    setImportBatch(null);
    setImportHistory([]);
    setTasks([]);
    setNotifications([]);
    setNotificationEmailStatus(null);
    setShowTaskForm(false);
    setTaskForm({
    client_id: "", title: "", description: "", kind: "document",
    priority: "normal", due_date: "", assigned_to_user_id: "",
  });
    setTaskClientFilter("all");
    setTaskSearch("");
    setError("");
    setSuccess("");
    setCurrentPage("dashboard");
  }

  if (publicUploadToken) return <PublicDocumentUploadPage token={publicUploadToken}/>;

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
  const canImportClients = ["owner", "admin", "accountant", "assistant"].includes(me.user.role);
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
          {canImportClients && <button className={currentPage === "imports" ? "nav-item selected" : "nav-item"} onClick={() => setCurrentPage("imports")}><ArrowDownToLine size={18} /><span>Importações</span></button>}
          <button className={currentPage === "tasks" ? "nav-item selected" : "nav-item"} onClick={() => setCurrentPage("tasks")}><ClipboardList size={18}/><span>Pendências e documentos</span><span className="nav-count">{tasks.filter(task => ["open", "received"].includes(task.status)).length}</span></button>
          <button className={currentPage === "notifications" ? "nav-item selected" : "nav-item"} onClick={() => setCurrentPage("notifications")}><Bell size={18}/><span>Notificações</span>{notifications.filter(item => !item.is_read).length > 0 && <span className="nav-count">{Math.min(notifications.filter(item => !item.is_read).length, 99)}</span>}</button>
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
          <div className="breadcrumb"><span>UnikSistemas</span><span className="crumb-divider">/</span><strong>{currentPage === "dashboard" ? "Visão geral" : currentPage === "clients" ? "Clientes" : currentPage === "imports" ? "Importações" : currentPage === "tasks" ? "Pendências e documentos" : currentPage === "notifications" ? "Notificações" : "Equipe"}</strong></div>
          <div className="topbar-actions"><span className="environment-tag"><i /> Ambiente de trabalho</span><button className="icon-button" type="button" title="Ajuda" onClick={() => setSuccess("Consulte a documentação da API em /docs no ambiente local.")}><CircleHelp size={18} /></button><button className="icon-button notification-bell-button" type="button" title="Abrir notificações" onClick={() => setCurrentPage("notifications")} aria-label={notifications.filter(item => !item.is_read).length ? `Notificações (${notifications.filter(item => !item.is_read).length} não lidas)` : "Notificações"}><Bell size={18} />{notifications.filter(item => !item.is_read).length > 0 && <span className="notification-bell-count">{Math.min(notifications.filter(item => !item.is_read).length, 99)}</span>}</button><div className="topbar-avatar">{initials(me.user.full_name)}</div></div>
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
              <section className="next-step-card"><div className="next-step-icon"><Activity size={20}/></div><div><span className="next-step-label">PRÓXIMA ETAPA</span><h3>Organize a base de atendimento</h3><p>Cadastre empresas manualmente ou importe uma planilha com prévia e validação. Acompanhamento de pendências será adicionado em uma próxima etapa.</p></div><button className="button button-secondary" onClick={() => setCurrentPage("clients")}>Abrir clientes <ArrowRight size={16}/></button></section>
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
          ) : currentPage === "users" ? (
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

          ) : currentPage === "notifications" ? (
            <>
              <div className="page-heading notification-page-heading">
                <div><div className="eyebrow">CENTRAL DE AVISOS · ESCRITÓRIO</div><h1>Notificações</h1><p>Acompanhe documentos recebidos, tarefas atribuídas e prazos próximos ou vencidos.</p></div>
                <div className="notification-page-actions">
                  {notifications.some(item => !item.is_read) && <button className="button button-secondary" disabled={notificationActionBusy !== null} onClick={() => void handleMarkAllNotificationsRead()}><CheckCheck size={15}/>{notificationActionBusy === "all" ? "Atualizando..." : "Marcar todas como lidas"}</button>}
                  <button className="icon-button" aria-label="Atualizar notificações" title="Atualizar notificações" disabled={notificationsLoading} onClick={() => void loadNotifications(token, ["owner", "admin"].includes(me.user.role))}><RefreshCw size={16}/></button>
                </div>
              </div>
              {["owner", "admin"].includes(me.user.role) && (
                <section className="content-card notification-email-card">
                  <div className="card-heading">
                    <div><h2>Alertas por e-mail</h2><p>{notificationEmailStatus?.note || "Consultando a configuração do envio..."}</p></div>
                    <div className="team-card-icon"><Mail size={18}/></div>
                  </div>
                  <div className="notification-email-metrics">
                    <div><span>SMTP</span><strong className={notificationEmailStatus?.configured ? "notification-email-ready" : "notification-email-off"}>{notificationEmailStatus?.configured ? "Configurado" : "Desativado"}</strong></div>
                    <div><span>Na fila</span><strong>{notificationEmailStatus?.pending ?? "—"}</strong></div>
                    <div><span>Falhas</span><strong>{notificationEmailStatus?.failed ?? "—"}</strong></div>
                  </div>
                  <div className="notification-email-footer">
                    <p>Os lembretes automáticos são gerados pelo worker. Para enviar e-mails, configure SMTP no ambiente e habilite <code>EMAIL_NOTIFICATIONS_ENABLED</code>.</p>
                    <button className="button button-secondary" disabled={notificationActionBusy !== null} onClick={() => void handleProcessDueReminders()}><CalendarDays size={15}/>{notificationActionBusy === "due-reminders" ? "Verificando..." : "Verificar prazos agora"}</button>
                  </div>
                  {!notificationEmailStatus?.configured && <p className="permissions-note"><LockKeyhole size={14}/> O sistema mantém os avisos na caixa interna e não envia e-mails enquanto SMTP estiver desativado.</p>}
                </section>
              )}
              <section className="content-card notification-list-card">
                <div className="card-heading"><div><h2>Seus avisos</h2><p>{notifications.filter(item => !item.is_read).length} não lida(s) nesta lista.</p></div><span className="notification-list-count">{notifications.length} de até 100</span></div>
                {notificationsLoading && notifications.length === 0 ? (
                  <div className="loading-state"><div className="spinner"/><span>Carregando notificações...</span></div>
                ) : notifications.length === 0 ? (
                  <div className="import-history-empty"><Bell size={24}/><strong>Nenhuma notificação por enquanto</strong><p>Novas atribuições, documentos recebidos e lembretes de prazo aparecerão aqui.</p></div>
                ) : (
                  <div className="notification-list">
                    {notifications.map(item => (
                      <article className={item.is_read ? "notification-row read" : "notification-row unread"} key={item.id}>
                        <div className={"notification-kind-icon notification-kind-" + item.event_type}>
                          {item.event_type === "document_received" ? <FileText size={17}/> : item.event_type === "task_assigned" ? <Users size={17}/> : <CalendarDays size={17}/>}
                        </div>
                        <div className="notification-main">
                          <div className="notification-title-line"><strong>{item.title}</strong><span className="notification-kind-label">{notificationKindLabel(item.event_type)}</span></div>
                          <p>{item.message}</p>
                          <div className="notification-meta"><span>{formatDateTime(item.created_at)}</span><span className={"notification-email-status email-" + item.email_status}>{notificationEmailLabels[item.email_status]}</span></div>
                        </div>
                        <div className="notification-actions">
                          {item.action_url && <button className="button button-secondary notification-action-button" onClick={() => void handleOpenNotification(item)}>{item.is_read ? "Abrir pendências" : "Ver aviso"} <ArrowRight size={13}/></button>}
                          {!item.is_read && <button className="icon-button" title="Marcar como lida" aria-label="Marcar como lida" disabled={notificationActionBusy !== null} onClick={() => void handleMarkNotificationRead(item.id)}><Check size={15}/></button>}
                          {["owner", "admin"].includes(me.user.role) && item.email_status === "failed" && <button className="text-button notification-retry-button" disabled={notificationActionBusy !== null} onClick={() => void handleRetryNotificationEmail(item.id)}>{notificationActionBusy === item.id ? "Reenfileirando..." : "Tentar novamente"}</button>}
                        </div>
                      </article>
                    ))}
                  </div>
                )}
                <div className="table-footer"><span>Dados restritos ao usuário autenticado</span><span>Últimas 100 notificações</span></div>
              </section>
              <p className="permissions-note"><ShieldCheck size={14}/> Cada usuário vê apenas as próprias notificações. Falhas de entrega não removem o aviso interno; um administrador pode reenfileirar e-mails após corrigir a configuração SMTP.</p>
            </>
          ) : currentPage === "tasks" ? (
            <>
              <div className="page-heading task-page-heading">
                <div><div className="eyebrow">ROTINA DO ESCRITÓRIO · ACOMPANHAMENTO</div><h1>Pendências e documentos</h1><p>Controle solicitações, prazos e responsáveis por cliente, sem perder o histórico do trabalho.</p></div>
                {["owner", "admin", "accountant", "assistant"].includes(me.user.role) && <button className="button button-primary" onClick={() => setShowTaskForm(value => !value)}><Plus size={16}/>{showTaskForm ? "Fechar formulário" : "Nova pendência"}</button>}
              </div>
              {showTaskForm && <section className="content-card create-card task-create-card">
                <div className="card-heading"><div><h2>Registrar pendência</h2><p>Selecione o cliente, descreva o que precisa ser recebido ou acompanhado e defina o prazo.</p></div><div className="team-card-icon"><ClipboardList size={18}/></div></div>
                {clients.filter(client => client.status === "active").length === 0 ? <div className="empty-state"><p>Cadastre um cliente ativo antes de registrar uma pendência.</p><button className="button button-secondary" onClick={() => setCurrentPage("clients")}>Abrir clientes</button></div> : <form className="client-form task-form" onSubmit={handleCreateTask}>
                  <div className="field field-wide"><label htmlFor="task-client">Cliente *</label><select id="task-client" value={taskForm.client_id} onChange={event => setTaskForm({...taskForm, client_id:event.target.value})} required><option value="">Selecione um cliente</option>{clients.filter(client => client.status === "active").map(client => <option key={client.id} value={client.id}>{client.trade_name || client.legal_name}</option>)}</select></div>
                  <div className="field field-wide"><label htmlFor="task-title">Pendência / documento solicitado *</label><input id="task-title" value={taskForm.title} onChange={event => setTaskForm({...taskForm, title:event.target.value})} required minLength={2} maxLength={200} placeholder="Ex.: Extratos bancários de setembro"/></div>
                  <div className="field field-wide"><label htmlFor="task-description">Descrição / orientação</label><textarea id="task-description" value={taskForm.description} onChange={event => setTaskForm({...taskForm, description:event.target.value})} maxLength={2000} rows={3} placeholder="Detalhes úteis para quem vai atender a solicitação"/></div>
                  <div className="field"><label htmlFor="task-kind">Tipo *</label><select id="task-kind" value={taskForm.kind} onChange={event => setTaskForm({...taskForm,kind:event.target.value as ClientTask["kind"]})}><option value="document">Documento solicitado</option><option value="follow_up">Acompanhamento do cliente</option><option value="routine">Rotina interna</option></select></div>
                  <div className="field"><label htmlFor="task-priority">Prioridade *</label><select id="task-priority" value={taskForm.priority} onChange={event => setTaskForm({...taskForm,priority:event.target.value as ClientTask["priority"]})}><option value="low">Baixa</option><option value="normal">Normal</option><option value="high">Alta</option></select></div>
                  <div className="field"><label htmlFor="task-due-date">Prazo</label><input id="task-due-date" type="date" value={taskForm.due_date} onChange={event => setTaskForm({...taskForm,due_date:event.target.value})}/></div>
                  <div className="field"><label htmlFor="task-assignee">Responsável interno</label><select id="task-assignee" value={taskForm.assigned_to_user_id} onChange={event => setTaskForm({...taskForm,assigned_to_user_id:event.target.value})}><option value="">Atribuir a mim ({me.user.full_name})</option>{users.filter(user => user.is_active).map(user => <option key={user.id} value={user.id}>{user.full_name} · {user.email}</option>)}</select></div>
                  <div className="form-actions"><span className="form-hint">Nenhum e-mail ou obrigação fiscal será enviado automaticamente.</span><button type="button" className="button button-secondary" onClick={() => setShowTaskForm(false)}>Cancelar</button><button type="submit" className="button button-primary" disabled={taskBusy}>{taskBusy ? "Salvando..." : "Registrar pendência"} {!taskBusy && <Check size={16}/>}</button></div>
                </form>}
              </section>}
              <section className="metric-grid task-metric-grid">
                <div className="metric-card"><div className="metric-top"><span>Pendentes</span><div className="metric-icon icon-amber"><Clock3 size={18}/></div></div><div className="metric-value">{tasks.filter(task => task.status === "open").length.toString().padStart(2, "0")}</div><div className="metric-foot"><span className="metric-neutral">Aguardando ação</span><span className="metric-foot-label">ABERTAS</span></div></div>
                <div className="metric-card"><div className="metric-top"><span>Documentos recebidos</span><div className="metric-icon icon-indigo"><FileText size={18}/></div></div><div className="metric-value">{tasks.filter(task => task.status === "received").length.toString().padStart(2, "0")}</div><div className="metric-foot"><span className="metric-neutral">Em conferência</span><span className="metric-foot-label">RECEBIDOS</span></div></div>
                <div className="metric-card"><div className="metric-top"><span>Concluídos</span><div className="metric-icon icon-green"><Check size={18}/></div></div><div className="metric-value">{tasks.filter(task => task.status === "completed").length.toString().padStart(2, "0")}</div><div className="metric-foot"><span className="metric-neutral">Trabalho encerrado</span><span className="metric-foot-label">FINALIZADOS</span></div></div>
              </section>
              <section className="content-card task-list-card">
                <div className="client-toolbar task-toolbar">
                  <div className="search-box"><Search size={17}/><input value={taskSearch} onChange={event => setTaskSearch(event.target.value)} placeholder="Buscar tarefa, cliente ou responsável..." aria-label="Buscar pendências"/>{taskSearch && <button onClick={() => setTaskSearch("")} aria-label="Limpar busca"><X size={15}/></button>}</div>
                  <div className="filter-group task-status-filters" aria-label="Filtrar por situação">
                    {([{value:"open",label:"Pendentes"},{value:"received",label:"Recebidos"},{value:"completed",label:"Concluídos"},{value:"all",label:"Todos"}] as const).map(filter => <button key={filter.value} className={taskFilter === filter.value ? "filter active" : "filter"} onClick={() => setTaskFilter(filter.value)}>{filter.label}<span>{filter.value === "all" ? tasks.length : tasks.filter(task => task.status === filter.value).length}</span></button>)}
                  </div>
                  <div className="task-client-filter"><label htmlFor="task-filter-client">Cliente</label><select id="task-filter-client" value={taskClientFilter} onChange={event => setTaskClientFilter(event.target.value)}><option value="all">Todos os clientes</option>{clients.map(client => <option key={client.id} value={client.id}>{client.trade_name || client.legal_name}</option>)}</select><button className="icon-button" onClick={() => void loadClientTasks(token)} disabled={tasksLoading} title="Atualizar pendências e documentos" aria-label="Atualizar pendências e documentos"><RefreshCw size={15}/></button></div>
                </div>
                {tasksLoading ? <div className="loading-state"><div className="spinner"/><span>Carregando pendências...</span></div> : filteredTasks.length === 0 ? <div className="import-history-empty"><ClipboardList size={24}/><strong>Nenhuma pendência neste filtro</strong><p>Cadastre uma nova pendência ou ajuste os filtros.</p></div> : (
                  <div className="task-list">
                    {filteredTasks.map(task => {
                      const primaryAction = task.status === "completed" || task.status === "cancelled"
                        ? {label:"Reabrir", status:"open" as TaskStatus}
                        : task.kind === "document" && task.status === "open"
                          ? {label:"Marcar recebido", status:"received" as TaskStatus}
                          : {label:"Concluir", status:"completed" as TaskStatus};
                      const overdue = task.due_date && task.due_date < new Date().toISOString().slice(0,10) && !["completed","cancelled"].includes(task.status);
                      const canEditTasks = ["owner", "admin", "accountant", "assistant"].includes(me.user.role);
                      return <article className="task-row" key={task.id}>
                        <div className="task-main">
                          <div className="task-kind-icon">{task.kind === "document" ? <FileText size={18}/> : task.kind === "follow_up" ? <Users size={18}/> : <ClipboardList size={18}/>}</div>
                          <div className="task-title-block"><strong>{task.title}</strong><span>{task.client_name}</span>{task.description && <p>{task.description}</p>}</div>
                        </div>
                        <div className="task-meta"><span className={`task-priority priority-${task.priority}`}>{taskPriorityLabels[task.priority]}</span><span className="task-kind-label">{taskKindLabels[task.kind]}</span></div>
                        <div className="task-deadline"><CalendarDays size={14}/><span className={overdue ? "task-overdue" : ""}>{task.due_date ? formatDate(task.due_date) : "Sem prazo"}{overdue ? " · Atrasada" : ""}</span></div>
                        <div className="task-assignee"><small>RESPONSÁVEL</small><span>{task.assigned_to_name || "Não atribuído"}</span></div>
                        <div className="task-status-cell"><span className={`status-pill ${task.status === "completed" ? "status-active" : task.status === "open" ? "status-pending" : "status-archived"}`}><i/>{taskStatusLabels[task.status]}</span>{canEditTasks && <div className="task-actions"><button className="button button-secondary task-action-button" disabled={taskBusy} onClick={() => void handleUpdateTask(task.id, {status:primaryAction.status})}>{primaryAction.label}</button>{!["completed","cancelled"].includes(task.status) && <button className="text-button task-cancel-button" disabled={taskBusy} onClick={() => void handleUpdateTask(task.id, {status:"cancelled"})}>Cancelar</button>}</div>}</div>
                        {task.kind === "document" && (() => {
                          const taskDocuments = documents.filter(document => document.task_id === task.id);
                          const activeLink = taskUploadLinks[task.id];
                          return <div className="task-documents">
                            <div className="task-documents-head"><strong>Arquivos recebidos · {taskDocuments.length}</strong>{canEditTasks && !["completed","cancelled"].includes(task.status) && <button className="button button-secondary task-action-button" disabled={taskLinkBusy === task.id} onClick={() => void handleCreateUploadLink(task.id)}>{taskLinkBusy === task.id ? "Gerando..." : activeLink ? "Gerar novo link" : "Gerar link temporário"}</button>}</div>
                            {activeLink && <div className="task-upload-link"><label>Link temporário — copie e envie ao cliente</label><div className="task-link-copy-row"><input aria-label="Link temporário de envio" readOnly value={activeLink.url}/><button className="button button-secondary task-action-button" onClick={() => void handleCopyUploadLink(activeLink.url)}>Copiar</button><button className="text-button task-cancel-button" onClick={() => void handleRevokeUploadLink(task.id)} disabled={taskLinkBusy === task.id}>Revogar</button></div><small>Expira em {formatDateTime(activeLink.expires_at)} · até 5 arquivos.</small></div>}
                            {taskDocuments.length === 0 ? <p className="task-no-documents">Nenhum arquivo recebido ainda.</p> : <div className="task-document-list">{taskDocuments.map(document => <div className="task-document-row" key={document.id}><div className="task-document-info"><strong>{document.original_filename}</strong><small>{fileSizeLabel(document.file_size)} · {documentReviewLabels[document.review_status]} · {formatDateTime(document.created_at)}</small>{document.review_note && <p>{document.review_note}</p>}</div><button className="button button-secondary task-action-button" onClick={() => void handleDownloadDocument(document.id, document.original_filename)}><Download size={13}/> Baixar</button>{canEditTasks && document.review_status === "pending" && <><button className="text-button task-document-accept" disabled={taskBusy} onClick={() => void handleReviewDocument(document.id, "accepted")}>Conferido</button><button className="text-button task-cancel-button" disabled={taskBusy} onClick={() => void handleReviewDocument(document.id, "rejected")}>Pedir correção</button></>}</div>)}</div>}
                          </div>;
                        })()}
                      </article>;
                    })}
                  </div>
                )}
                <div className="table-footer"><span>Exibindo <strong>{filteredTasks.length}</strong> de <strong>{tasks.length}</strong> pendências</span><span>Dados do escritório autenticado</span></div>
              </section>
              <p className="permissions-note"><LockKeyhole size={14}/> As pendências são vinculadas a clientes e usuários do escritório autenticado. Alterações geram registro de auditoria; o sistema não dispara mensagens nem executa rotinas fiscais automaticamente.</p>
            </>
          ) : (
            <>
              <div className="page-heading import-page-heading">
                <div><div className="eyebrow">IMPORTAÇÃO · BASE DE CLIENTES</div><h1>Importação assistida</h1><p>Baixe um modelo, preencha os dados e valide antes de importar.</p></div>
                <div className="import-template-actions">
                  <button className="button button-secondary" onClick={() => void handleDownloadTemplate("csv")} disabled={templateBusy !== null}>
                    <Download size={15}/>{templateBusy === "csv" ? "Baixando..." : "Modelo CSV"}
                  </button>
                  <button className="button button-secondary" onClick={() => void handleDownloadTemplate("xlsx")} disabled={templateBusy !== null}>
                    <FileSpreadsheet size={15}/>{templateBusy === "xlsx" ? "Baixando..." : "Modelo Excel"}
                  </button>
                </div>
              </div>
              <section className="content-card import-upload-card">
                <div className="card-heading">
                  <div><h2>Enviar planilha</h2><p>Formatos aceitos: CSV ou Excel (.xlsx). Até 5 MiB e 1.000 linhas por arquivo.</p></div>
                  <div className="team-card-icon"><ArrowDownToLine size={18}/></div>
                </div>
                <form className="import-form" onSubmit={handlePreviewImport}>
                  <label className="import-file-label" htmlFor="client-import-file">
                    <span className="import-file-icon"><FileText size={24}/></span>
                    <strong>{importFile ? importFile.name : "Escolha sua planilha"}</strong>
                    <small>{importFile ? "Arquivo selecionado · clique para trocar" : "Clique para selecionar um arquivo CSV ou XLSX"}</small>
                    <input
                      id="client-import-file"
                      type="file"
                      accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                      onChange={event => { setImportFile(event.target.files?.[0] ?? null); setError(""); setSuccess(""); }}
                      disabled={importBusy || confirmImportBusy}
                      required
                    />
                  </label>
                  <div className="import-help">
                    <strong>Colunas reconhecidas</strong>
                    <p><b>Obrigatória:</b> Razão Social (ou <code>legal_name</code>).</p>
                    <p><b>Opcionais:</b> Nome Fantasia, CNPJ/CPF, E-mail, Telefone e Status (Ativo/Arquivado). A primeira linha deve conter os títulos das colunas.</p>
                  </div>
                  <div className="form-actions">
                    <span className="form-hint">A prévia não grava nenhum cliente.</span>
                    <button type="submit" className="button button-primary" disabled={!importFile || importBusy}>
                      {importBusy ? "Validando arquivo..." : "Validar e visualizar"} {!importBusy && <ArrowDownToLine size={16}/>}
                    </button>
                  </div>
                </form>
              </section>
              {importBatch && (
                <section className="content-card import-preview-card">
                  <div className="card-heading import-preview-heading">
                    <div>
                      <h2>{importBatch.status === "confirmed" ? "Importação concluída" : importBatch.status === "discarded" ? "Prévia descartada" : "Prévia e validação"}</h2>
                      <p><strong>{importBatch.filename}</strong> · {importBatch.total_rows} linha(s) analisada(s). {importBatch.status === "ready" ? "Nenhuma pendência encontrada." : importBatch.status === "confirmed" ? "Os clientes foram importados." : importBatch.status === "discarded" ? "Nenhum cliente foi importado por este lote." : "Há linhas que precisam de correção."}</p>
                    </div>
                    <span className={`status-pill ${importStatusClass(importBatch.status)}`}>
                      <i/>{importStatusLabel(importBatch.status)}
                    </span>
                  </div>
                  {["ready", "invalid"].includes(importBatch.status) && <div className="import-preview-scroll">
                    <table className="import-preview-table">
                      <thead><tr><th>Linha</th><th>Razão social</th><th>Nome fantasia</th><th>CNPJ/CPF</th><th>E-mail</th><th>Telefone</th><th>Situação</th><th>Validação</th></tr></thead>
                      <tbody>{importBatch.rows.map(row => (
                        <tr key={row.row_number} className={row.errors.length ? "import-row-invalid" : ""}>
                          <td>{row.row_number}</td><td>{row.legal_name || "—"}</td><td>{row.trade_name || "—"}</td><td>{row.tax_id || "—"}</td><td>{row.email || "—"}</td><td>{row.phone || "—"}</td><td>{row.status === "active" ? "Ativo" : row.status === "archived" ? "Arquivado" : row.status || "—"}</td>
                          <td>{row.errors.length ? <ul className="import-errors">{row.errors.map((message, index) => <li key={index}>{message}</li>)}</ul> : <span className="import-row-ok"><Check size={14}/> OK</span>}</td>
                        </tr>
                      ))}</tbody>
                    </table>
                  </div>}
                  <div className="import-confirm-footer">
                    <p>{importBatch.status === "invalid" ? "Nenhum dado foi gravado. Corrija as linhas sinalizadas no arquivo original e envie novamente." : importBatch.status === "confirmed" ? `${importBatch.imported_count} cliente(s) foram adicionados à base deste escritório.` : importBatch.status === "discarded" ? "Esta prévia foi descartada. O registro permanece no histórico, sem os dados pessoais da planilha." : "Confira as informações acima. Só depois de confirmar os clientes serão gravados."}</p>
                    {["ready", "invalid"].includes(importBatch.status) && <div className="import-preview-actions">
                      <button className="button button-secondary" onClick={() => void handleDiscardImport()} disabled={importBusy || confirmImportBusy}>Descartar prévia</button>
                      {importBatch.status === "ready" && <button className="button button-primary" onClick={() => void handleConfirmImport()} disabled={confirmImportBusy || importBusy}>{confirmImportBusy ? "Importando..." : `Confirmar e importar ${importBatch.total_rows} cliente(s)`} {!confirmImportBusy && <Check size={16}/>}</button>}
                    </div>}
                  </div>
                </section>
              )}
              <section className="content-card import-history-card">
                <div className="card-heading">
                  <div><h2>Histórico de importações</h2><p>Últimos 50 lotes enviados neste escritório.</p></div>
                  <button className="icon-button" onClick={() => void loadImportHistory(token)} disabled={historyLoading} aria-label="Atualizar histórico" title="Atualizar histórico"><RefreshCw size={16}/></button>
                </div>
                {historyLoading && importHistory.length === 0 ? (
                  <div className="import-history-empty"><span className="spinner"/><p>Carregando histórico...</p></div>
                ) : importHistory.length === 0 ? (
                  <div className="import-history-empty"><Clock3 size={24}/><strong>Nenhuma importação registrada</strong><p>Após enviar sua primeira planilha, o histórico aparecerá aqui.</p></div>
                ) : (
                  <div className="import-history-scroll">
                    <table className="import-history-table">
                      <thead><tr><th>ARQUIVO</th><th>DATA</th><th>ENVIADO POR</th><th>LINHAS</th><th>IMPORTADOS</th><th>SITUAÇÃO</th><th/></tr></thead>
                      <tbody>{importHistory.map(entry => (
                        <tr key={entry.id}>
                          <td><div className="import-history-file"><FileText size={15}/><span>{entry.filename}</span></div></td>
                          <td>{formatDateTime(entry.created_at)}</td>
                          <td>{entry.created_by_name || "Usuário removido"}</td>
                          <td>{entry.total_rows}</td>
                          <td><strong>{entry.imported_count}</strong></td>
                          <td><span className={`status-pill ${importStatusClass(entry.status)}`}><i/>{importStatusLabel(entry.status)}</span></td>
                          <td>{["ready", "invalid"].includes(entry.status) && <button className="text-button" onClick={() => void handleOpenImportHistory(entry.id)}>Ver prévia <ArrowRight size={14}/></button>}</td>
                        </tr>
                      ))}</tbody>
                    </table>
                  </div>
                )}
              </section>
              <p className="permissions-note"><LockKeyhole size={14}/> O histórico é restrito ao escritório autenticado. O arquivo original não é armazenado; prévias pendentes podem ser descartadas, e seu conteúdo é removido após confirmação ou descarte.</p>
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
