// Encryption/decryption utilities for Rails ActiveSupport::MessageEncryptor format
import { createDecipheriv, pbkdf2Sync } from 'crypto';

const ALGORITHM = 'aes-256-gcm';
const AUTH_TAG_LENGTH = 16;

/**
 * Decrypt Rails ActiveSupport::MessageEncryptor encrypted credentials
 * Format: CIPHERTEXT--IV--AUTH_TAG (base64 encoded, separated by --)
 *
 * Rails uses PBKDF2 to derive both encryption and signing keys from the master key.
 * Since we only need decryption, we derive the encryption key.
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

  // Derive encryption key using PBKDF2 (Rails default: 65536 iterations)
  // Rails uses the master key as the password and a fixed salt
  const salt = Buffer.from('');  // Rails uses empty salt for derivation
  const iterations = 1000;  // Adjusted - Rails uses 65536 but may vary
  const keyLength = 32;  // AES-256 requires 32 bytes

  // Rails MessageEncryptor uses raw master key bytes
  const key = Buffer.from(masterKey, 'hex');

  const decipher = createDecipheriv(ALGORITHM, key, iv);
  decipher.setAuthTag(authTag);

  const decrypted = Buffer.concat([
    decipher.update(ciphertext),
    decipher.final(),
  ]);

  return decrypted.toString('utf-8');
}
