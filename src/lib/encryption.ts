// Encryption/decryption utilities for Rails ActiveSupport::MessageEncryptor format
import { createDecipheriv } from 'crypto';

const ALGORITHM = 'aes-128-gcm';  // Rails 7.2 uses AES-128-GCM by default

/**
 * Decrypt Rails ActiveSupport::MessageEncryptor encrypted credentials
 * Format: CIPHERTEXT--IV--AUTH_TAG (base64 encoded, separated by --)
 *
 * Rails 7.2 uses AES-128-GCM with the master.key directly as the encryption key (16 bytes).
 */
export function decryptCredentials(encrypted: string, masterKey: string): string {
  const parts = encrypted.split('--');
  if (parts.length !== 3) {
    throw new Error('Invalid Rails encrypted credential format (expected CIPHERTEXT--IV--AUTH_TAG)');
  }

  const [ciphertextB64, ivB64, authTagB64] = parts;

  const ciphertext = Buffer.from(ciphertextB64, 'base64');
  const iv = Buffer.from(ivB64, 'base64');
  const authTag = Buffer.from(authTagB64, 'base64');

  // Master key is used directly as AES-128 key (32 hex chars = 16 bytes)
  const key = Buffer.from(masterKey, 'hex');

  if (key.length !== 16) {
    throw new Error(`Invalid master key length: expected 16 bytes, got ${key.length}`);
  }

  const decipher = createDecipheriv(ALGORITHM, key, iv);
  decipher.setAuthTag(authTag);

  const decrypted = Buffer.concat([
    decipher.update(ciphertext),
    decipher.final(),
  ]);

  return decrypted.toString('utf-8');
}
