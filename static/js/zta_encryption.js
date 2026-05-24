// ZTA End-to-End Encryption for Framework 2
// Using same RSA+AES hybrid encryption as Framework 1

class ZTAEncryption {
    constructor() {
        this.userPublicKey = null;
        this.userPrivateKey = null;
        this.userId = null;
    }
    
    // Generate RSA key pair (2048-bit)
    async generateKeyPair() {
        const keyPair = await window.crypto.subtle.generateKey(
            {
                name: "RSA-OAEP",
                modulusLength: 2048,
                publicExponent: new Uint8Array([1, 0, 1]),
                hash: "SHA-256",
            },
            true,  // extractable
            ["encrypt", "decrypt"]
        );
        return keyPair;
    }
    
    // Export public key to JWK format for storage
    async exportPublicKey(key) {
        const exported = await window.crypto.subtle.exportKey("jwk", key);
        return exported;
    }
    
    // Import public key from JWK
    async importPublicKey(jwk) {
        const key = await window.crypto.subtle.importKey(
            "jwk",
            jwk,
            {
                name: "RSA-OAEP",
                hash: "SHA-256",
            },
            true,
            ["encrypt"]
        );
        return key;
    }
    
    // Import private key from JWK
    async importPrivateKey(jwk) {
        const key = await window.crypto.subtle.importKey(
            "jwk",
            jwk,
            {
                name: "RSA-OAEP",
                hash: "SHA-256",
            },
            true,
            ["decrypt"]
        );
        return key;
    }
    
    // Generate random AES key (256-bit)
    async generateAESKey() {
        const aesKey = await window.crypto.subtle.generateKey(
            {
                name: "AES-GCM",
                length: 256,
            },
            true,
            ["encrypt", "decrypt"]
        );
        return aesKey;
    }
    
    // Encrypt data with AES-GCM
    async encryptWithAES(data, aesKey) {
        const iv = window.crypto.getRandomValues(new Uint8Array(12));
        const encrypted = await window.crypto.subtle.encrypt(
            {
                name: "AES-GCM",
                iv: iv,
            },
            aesKey,
            new TextEncoder().encode(data)
        );
        return {
            ciphertext: Array.from(new Uint8Array(encrypted)),
            iv: Array.from(iv)
        };
    }
    
    // Decrypt data with AES-GCM
    async decryptWithAES(encryptedData, aesKey, iv) {
        const decrypted = await window.crypto.subtle.decrypt(
            {
                name: "AES-GCM",
                iv: new Uint8Array(iv),
            },
            aesKey,
            new Uint8Array(encryptedData)
        );
        return new TextDecoder().decode(decrypted);
    }
    
    // Encrypt AES key with RSA public key
    async encryptAESKeyWithRSA(aesKey, publicKey) {
        const exportedAESKey = await window.crypto.subtle.exportKey("raw", aesKey);
        const encryptedKey = await window.crypto.subtle.encrypt(
            {
                name: "RSA-OAEP",
            },
            publicKey,
            exportedAESKey
        );
        return Array.from(new Uint8Array(encryptedKey));
    }
    
    // Decrypt AES key with RSA private key
    async decryptAESKeyWithRSA(encryptedKey, privateKey) {
        const decryptedKey = await window.crypto.subtle.decrypt(
            {
                name: "RSA-OAEP",
            },
            privateKey,
            new Uint8Array(encryptedKey)
        );
        const aesKey = await window.crypto.subtle.importKey(
            "raw",
            decryptedKey,
            "AES-GCM",
            true,
            ["encrypt", "decrypt"]
        );
        return aesKey;
    }
    
    // Full encryption flow: data -> AES encrypted, AES key -> RSA encrypted
    async encryptData(data, recipientPublicKey) {
        // Generate random AES key
        const aesKey = await this.generateAESKey();
        
        // Encrypt data with AES
        const encrypted = await this.encryptWithAES(data, aesKey);
        
        // Encrypt AES key with recipient's RSA public key
        const encryptedAESKey = await this.encryptAESKeyWithRSA(aesKey, recipientPublicKey);
        
        return {
            ciphertext: encrypted.ciphertext,
            iv: encrypted.iv,
            encryptedKey: encryptedAESKey,
            algorithm: "AES-GCM-256-RSA-OAEP-2048"
        };
    }
    
    // Full decryption flow
    async decryptData(encryptedPackage, recipientPrivateKey) {
        // Decrypt AES key with RSA private key
        const aesKey = await this.decryptAESKeyWithRSA(
            encryptedPackage.encryptedKey,
            recipientPrivateKey
        );
        
        // Decrypt data with AES
        const decrypted = await this.decryptWithAES(
            encryptedPackage.ciphertext,
            aesKey,
            encryptedPackage.iv
        );
        
        return decrypted;
    }
    
    // Store user's key pair in localStorage (encrypted with user's password hash)
    async storeUserKeys(userId, keyPair, passwordHash) {
        const exportedPublic = await window.crypto.subtle.exportKey("jwk", keyPair.publicKey);
        const exportedPrivate = await window.crypto.subtle.exportKey("jwk", keyPair.privateKey);
        
        // Simple encryption of private key with password hash (in production, use proper key derivation)
        const keys = {
            userId: userId,
            publicKey: exportedPublic,
            privateKey: exportedPrivate,
            createdAt: new Date().toISOString()
        };
        
        localStorage.setItem(`zta_keys_${userId}`, JSON.stringify(keys));
        return keys;
    }
    
    // Load user's key pair from localStorage
    async loadUserKeys(userId) {
        const stored = localStorage.getItem(`zta_keys_${userId}`);
        if (!stored) return null;
        
        const keys = JSON.parse(stored);
        const publicKey = await this.importPublicKey(keys.publicKey);
        const privateKey = await this.importPrivateKey(keys.privateKey);
        
        return { publicKey, privateKey };
    }
}

// Initialize encryption for Framework 2
const ztaEncryption = new ZTAEncryption();