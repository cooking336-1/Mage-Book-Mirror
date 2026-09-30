/**
 * Offline PWA Storage with Field-Level Encrypted IndexedDB (MUC 3.1 & F7).
 *
 * Implements:
 * 1. Safe IndexedDB abstraction for offline invoice drafting and customer cache.
 * 2. Transparent AES-GCM 256-bit encryption/decryption of cached PII and financial drafts.
 * 3. Automatic background synchronization via window 'online' event listeners.
 * 4. Idempotent replay against backend POST /api/v1/invoicing/invoices/.
 */

import apiClient from "@/lib/apiClient";
import {
  deriveCacheKey,
  encryptInvoiceDraft,
  decryptInvoiceDraft,
  encryptCustomerCacheRecord,
  decryptCustomerCacheRecord,
  type OfflineInvoiceDraft,
  type EncryptedOfflineInvoiceDraft,
  type CustomerCacheRecord,
  type EncryptedCustomerCacheRecord,
} from "@/lib/crypto/pwa-cache-encryption";

const DB_NAME = "magebooks_offline_pwa_db";
const DB_VERSION = 1;

const STORES = {
  INVOICES: "offline_invoices",
  CUSTOMERS: "offline_customers",
} as const;

let dbInstance: IDBDatabase | null = null;
let cachedCryptoKey: CryptoKey | null = null;

/**
 * Checks whether IndexedDB and WebCrypto are available in current runtime.
 */
export function isOfflineStorageSupported(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof indexedDB !== "undefined" &&
    typeof globalThis.crypto?.subtle !== "undefined"
  );
}

/**
 * Opens and initializes the IndexedDB database instance with required object stores and indexes.
 */
export async function initOfflineDB(): Promise<IDBDatabase | null> {
  if (!isOfflineStorageSupported()) {
    return null;
  }

  if (dbInstance) {
    return dbInstance;
  }

  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);

    request.onupgradeneeded = (event) => {
      const db = (event.target as IDBOpenDBRequest).result;

      if (!db.objectStoreNames.contains(STORES.INVOICES)) {
        const invoiceStore = db.createObjectStore(STORES.INVOICES, { keyPath: "id" });
        invoiceStore.createIndex("organizationId", "organizationId", { unique: false });
        invoiceStore.createIndex("syncStatus", "syncStatus", { unique: false });
        invoiceStore.createIndex("createdAt", "createdAt", { unique: false });
      }

      if (!db.objectStoreNames.contains(STORES.CUSTOMERS)) {
        const customerStore = db.createObjectStore(STORES.CUSTOMERS, { keyPath: "id" });
        customerStore.createIndex("organizationId", "organizationId", { unique: false });
        customerStore.createIndex("name", "name", { unique: false });
      }
    };

    request.onsuccess = () => {
      dbInstance = request.result;
      resolve(dbInstance);
    };

    request.onerror = () => {
      reject(new Error(`Failed to open IndexedDB: ${request.error?.message}`));
    };
  });
}

/**
 * Derives or retrieves the cached 256-bit AES-GCM CryptoKey for this device session.
 */
export async function getOfflineStorageKey(): Promise<CryptoKey> {
  if (cachedCryptoKey) {
    return cachedCryptoKey;
  }

  // Derive key from a secure persistent device seed stored in localStorage
  let deviceSeed = typeof window !== "undefined" ? localStorage.getItem("magebooks_device_seed") : null;
  if (!deviceSeed) {
    const randomBytes = new Uint8Array(32);
    globalThis.crypto.getRandomValues(randomBytes);
    let binary = "";
    for (let i = 0; i < randomBytes.byteLength; i++) {
      binary += String.fromCharCode(randomBytes[i]);
    }
    deviceSeed = btoa(binary);
    if (typeof window !== "undefined") {
      localStorage.setItem("magebooks_device_seed", deviceSeed);
    }
  }

  cachedCryptoKey = await deriveCacheKey(deviceSeed);
  return cachedCryptoKey;
}

/**
 * Saves a new or updated invoice draft to local encrypted IndexedDB.
 */
export async function saveOfflineInvoice(draft: OfflineInvoiceDraft): Promise<void> {
  const db = await initOfflineDB();
  if (!db) {
    throw new Error("IndexedDB is not supported in this environment.");
  }

  const key = await getOfflineStorageKey();
  const encryptedRecord = await encryptInvoiceDraft(draft, key);

  return new Promise((resolve, reject) => {
    const transaction = db.transaction([STORES.INVOICES], "readwrite");
    const store = transaction.objectStore(STORES.INVOICES);
    const request = store.put(encryptedRecord);

    request.onsuccess = () => resolve();
    request.onerror = () => reject(new Error(`Failed to save offline invoice: ${request.error?.message}`));
  });
}

/**
 * Retrieves all offline invoice drafts (optionally filtered by tenant organization), decrypted to plaintext.
 */
export async function getOfflineInvoices(organizationId?: string): Promise<OfflineInvoiceDraft[]> {
  const db = await initOfflineDB();
  if (!db) {
    return [];
  }

  const key = await getOfflineStorageKey();

  return new Promise((resolve, reject) => {
    const transaction = db.transaction([STORES.INVOICES], "readonly");
    const store = transaction.objectStore(STORES.INVOICES);
    const request = store.getAll();

    request.onsuccess = async () => {
      try {
        const encryptedList: EncryptedOfflineInvoiceDraft[] = request.result || [];
        const filtered = organizationId
          ? encryptedList.filter((rec) => rec.organizationId === organizationId)
          : encryptedList;

        const decryptedList: OfflineInvoiceDraft[] = [];
        for (const enc of filtered) {
          try {
            const draft = await decryptInvoiceDraft(enc, key);
            decryptedList.push(draft);
          } catch (decryptErr) {
            console.error(`Failed to decrypt offline draft ${enc.id}:`, decryptErr);
          }
        }

        // Sort descending by creation timestamp
        decryptedList.sort((a, b) => b.createdAt - a.createdAt);
        resolve(decryptedList);
      } catch (err) {
        reject(err);
      }
    };

    request.onerror = () => reject(new Error(`Failed to read offline invoices: ${request.error?.message}`));
  });
}

/**
 * Deletes an offline invoice draft by ID after successful backend synchronization.
 */
export async function deleteOfflineInvoice(id: string): Promise<void> {
  const db = await initOfflineDB();
  if (!db) return;

  return new Promise((resolve, reject) => {
    const transaction = db.transaction([STORES.INVOICES], "readwrite");
    const store = transaction.objectStore(STORES.INVOICES);
    const request = store.delete(id);

    request.onsuccess = () => resolve();
    request.onerror = () => reject(new Error(`Failed to delete offline invoice: ${request.error?.message}`));
  });
}

/**
 * Encrypts and caches customer details for offline invoice autocomplete.
 */
export async function saveOfflineCustomer(customer: CustomerCacheRecord): Promise<void> {
  const db = await initOfflineDB();
  if (!db) return;

  const key = await getOfflineStorageKey();
  const encrypted = await encryptCustomerCacheRecord(customer, key);

  return new Promise((resolve, reject) => {
    const transaction = db.transaction([STORES.CUSTOMERS], "readwrite");
    const store = transaction.objectStore(STORES.CUSTOMERS);
    const request = store.put(encrypted);

    request.onsuccess = () => resolve();
    request.onerror = () => reject(new Error(`Failed to cache customer: ${request.error?.message}`));
  });
}

/**
 * Retrieves and decrypts all cached customers for offline creation.
 */
export async function getOfflineCustomers(organizationId?: string): Promise<CustomerCacheRecord[]> {
  const db = await initOfflineDB();
  if (!db) return [];

  const key = await getOfflineStorageKey();

  return new Promise((resolve, reject) => {
    const transaction = db.transaction([STORES.CUSTOMERS], "readonly");
    const store = transaction.objectStore(STORES.CUSTOMERS);
    const request = store.getAll();

    request.onsuccess = async () => {
      try {
        const encryptedList: EncryptedCustomerCacheRecord[] = request.result || [];
        const filtered = organizationId
          ? encryptedList.filter((rec) => rec.organizationId === organizationId)
          : encryptedList;

        const decrypted: CustomerCacheRecord[] = [];
        for (const enc of filtered) {
          try {
            const customer = await decryptCustomerCacheRecord(enc, key);
            decrypted.push(customer);
          } catch (err) {
            console.error(`Failed to decrypt cached customer ${enc.id}:`, err);
          }
        }
        resolve(decrypted);
      } catch (err) {
        reject(err);
      }
    };

    request.onerror = () => reject(new Error(`Failed to read cached customers: ${request.error?.message}`));
  });
}

export interface SyncResult {
  synced: number;
  failed: number;
  errors: Array<{ id: string; error: string }>;
}

/**
 * Synchronizes pending offline drafts with backend REST API.
 * Uses Idempotency-Key headers to guarantee zero double-invoicing.
 */
export async function syncOfflineInvoices(client = apiClient): Promise<SyncResult> {
  if (!isOfflineStorageSupported()) {
    return { synced: 0, failed: 0, errors: [] };
  }

  const drafts = await getOfflineInvoices();
  const pending = drafts.filter((d) => d.syncStatus === "pending" || d.syncStatus === "failed");

  let synced = 0;
  let failed = 0;
  const errors: Array<{ id: string; error: string }> = [];

  for (const draft of pending) {
    try {
      // Mark as syncing in local DB
      draft.syncStatus = "syncing";
      await saveOfflineInvoice(draft);

      const payload = {
        customer_id: draft.customerId,
        issue_date: draft.issueDate,
        due_date: draft.dueDate,
        currency: draft.currency || "GHS",
        action: "save_draft",
        notes: draft.notes || "",
        lines: draft.lines.map((l) => ({
          description: l.description,
          quantity: l.quantity,
          unit_price: l.unitPrice,
          supply_type: l.supplyType || "STANDARD",
          account_id: l.accountId || null,
        })),
      };

      await client.post("/api/v1/invoicing/invoices/", payload, {
        headers: {
          "Idempotency-Key": `offline-draft-${draft.id}`,
          "X-Organization-ID": draft.organizationId,
        },
      });

      // Remove from offline queue upon successful commit
      await deleteOfflineInvoice(draft.id);
      synced++;
    } catch (err: unknown) {
      failed++;
      const msg = err instanceof Error ? err.message : String(err);
      draft.syncStatus = "failed";
      draft.syncError = msg;
      await saveOfflineInvoice(draft);
      errors.push({ id: draft.id, error: msg });
    }
  }

  if (typeof window !== "undefined" && synced > 0) {
    window.dispatchEvent(
      new CustomEvent("magebooks:offline-sync-complete", {
        detail: { synced, failed, errors },
      })
    );
  }

  return { synced, failed, errors };
}

/**
 * Registers global 'online' event listener to auto-sync when network reconnects.
 */
export function registerOfflineSyncListener(): () => void {
  if (typeof window === "undefined") {
    return () => {};
  }

  const handleOnline = () => {
    syncOfflineInvoices().catch((err) => {
      console.warn("Background offline sync failed:", err);
    });
  };

  window.addEventListener("online", handleOnline);
  return () => window.removeEventListener("online", handleOnline);
}
