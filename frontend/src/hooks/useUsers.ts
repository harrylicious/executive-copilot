import { useState, useEffect, useCallback } from "react";
import { toast } from "sonner";
import {
  getUsers,
  createUser,
  updateUser,
  deleteUser,
  type UserFilters,
  type UserCreate,
  type UserUpdate,
  type UserResponse,
} from "../api/users";

interface UseUsersReturn {
  users: UserResponse[];
  total: number;
  loading: boolean;
  error: string | null;
  fetchUsers: (filters?: UserFilters) => Promise<void>;
  handleCreate: (data: UserCreate) => Promise<void>;
  handleUpdate: (id: number, data: UserUpdate) => Promise<void>;
  handleDelete: (id: number) => Promise<void>;
  operationLoading: boolean;
  operationError: string | null;
}

export function useUsers(): UseUsersReturn {
  const [users, setUsers] = useState<UserResponse[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [operationLoading, setOperationLoading] = useState(false);
  const [operationError, setOperationError] = useState<string | null>(null);
  const [currentFilters, setCurrentFilters] = useState<UserFilters | undefined>();

  const fetchUsers = useCallback(async (filters?: UserFilters) => {
    setLoading(true);
    setError(null);
    setCurrentFilters(filters);

    try {
      const result = await getUsers(filters);
      setUsers(result.items);
      setTotal(result.total);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to load users";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleCreate = useCallback(
    async (data: UserCreate) => {
      setOperationLoading(true);
      setOperationError(null);

      try {
        await createUser(data);
        await fetchUsers(currentFilters);
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "Failed to create user";
        setOperationError(message);
        toast.error("Gagal membuat user", { description: message, duration: 5000 });
      } finally {
        setOperationLoading(false);
      }
    },
    [fetchUsers, currentFilters]
  );

  const handleUpdate = useCallback(
    async (id: number, data: UserUpdate) => {
      setOperationLoading(true);
      setOperationError(null);

      try {
        await updateUser(id, data);
        await fetchUsers(currentFilters);
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "Failed to update user";
        setOperationError(message);
        toast.error("Gagal memperbarui user", { description: message, duration: 5000 });
      } finally {
        setOperationLoading(false);
      }
    },
    [fetchUsers, currentFilters]
  );

  const handleDelete = useCallback(
    async (id: number) => {
      setOperationLoading(true);
      setOperationError(null);

      try {
        await deleteUser(id);
        await fetchUsers(currentFilters);
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "Failed to delete user";
        setOperationError(message);
        toast.error("Gagal menghapus user", { description: message, duration: 5000 });
      } finally {
        setOperationLoading(false);
      }
    },
    [fetchUsers, currentFilters]
  );

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  // Auto-dismiss operationError after 5 seconds
  useEffect(() => {
    if (!operationError) return;
    const timer = setTimeout(() => setOperationError(null), 5000);
    return () => clearTimeout(timer);
  }, [operationError]);

  return {
    users,
    total,
    loading,
    error,
    fetchUsers,
    handleCreate,
    handleUpdate,
    handleDelete,
    operationLoading,
    operationError,
  };
}

export default useUsers;
