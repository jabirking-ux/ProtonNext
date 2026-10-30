// -----------------------------------------------------------------------------
// Copyright (c) 2025 Proton AG
// -----------------------------------------------------------------------------

use proton_srp::{SRPAuth, SRPProofB64};
use std::ffi::{CStr, CString};
use std::os::raw::{c_char, c_int};
use std::slice;

const ERROR_CODE: c_int = -1;
const ERR_NULL_PARAMETER: &str = "One or more required parameters is null";
const ERR_PASSWORD_LENGTH: &str = "Password length must be greater than zero";
const ERR_INVALID_UTF8_PASSWORD: &str = "Invalid UTF-8 in password data";
const ERR_INVALID_UTF8_SALT: &str = "Invalid UTF-8 in salt parameter";
const ERR_INVALID_UTF8_MODULUS: &str = "Invalid UTF-8 in modulus parameter";
const ERR_INVALID_UTF8_CHALLENGE: &str = "Invalid UTF-8 in server_challenge parameter";
const ERR_CONVERT_CLIENT_EPHEMERAL: &str = "Failed to convert client_ephemeral to C string";
const ERR_CONVERT_CLIENT_PROOF: &str = "Failed to convert client_proof to C string";
const ERR_CONVERT_EXPECTED_SERVER_PROOF: &str = "Failed to convert expected_server_proof to C string";
const ERR_CREATE_SRP_CLIENT: &str = "Failed to create SRP client:";
const ERR_GENERATE_PROOFS: &str = "Failed to generate proofs:";

#[repr(C)]
pub struct CSRPProof {
    client_ephemeral: *mut c_char,
    client_proof: *mut c_char,
    expected_server_proof: *mut c_char,
}

/// # Safety
/// All pointer parameters must be valid and non-null. The password_data pointer must point to
/// a valid memory region of at least password_len bytes. String parameters (salt, modulus,
/// server_challenge) must be null-terminated C strings with valid UTF-8 encoding.
// nosem: rust.lang.security.unsafe-usage.unsafe-usage
#[unsafe(no_mangle)]
pub unsafe extern "C" fn generate_proof(
    password_data: *const u8,
    password_len: usize,
    salt: *const c_char,
    modulus: *const c_char,
    server_challenge: *const c_char,
    out_proof: *mut CSRPProof,
    out_error: *mut *mut c_char,
) -> c_int {
    if password_data.is_null()
        || salt.is_null()
        || modulus.is_null()
        || server_challenge.is_null()
        || out_proof.is_null()
    {
        set_error_message(out_error, ERR_NULL_PARAMETER);
        return ERROR_CODE;
    }

    if password_len == 0 {
        set_error_message(out_error, ERR_PASSWORD_LENGTH);
        return ERROR_CODE;
    }

    // nosem: rust.lang.security.unsafe-usage.unsafe-usage
    let password_slice = unsafe { slice::from_raw_parts(password_data, password_len) };
    let password_str = match String::from_utf8(password_slice.to_vec()) {
        Ok(s) => s,
        Err(_) => {
            set_error_message(out_error, ERR_INVALID_UTF8_PASSWORD);
            return ERROR_CODE;
        }
    };

    // nosem: rust.lang.security.unsafe-usage.unsafe-usage
    let salt_str = match unsafe { CStr::from_ptr(salt).to_str() } {
        Ok(s) => s,
        Err(_) => {
            set_error_message(out_error, ERR_INVALID_UTF8_SALT);
            return ERROR_CODE;
        }
    };

    // nosem: rust.lang.security.unsafe-usage.unsafe-usage
    let modulus_str = match unsafe { CStr::from_ptr(modulus).to_str() } {
        Ok(s) => s,
        Err(_) => {
            set_error_message(out_error, ERR_INVALID_UTF8_MODULUS);
            return ERROR_CODE;
        }
    };

    // nosem: rust.lang.security.unsafe-usage.unsafe-usage
    let challenge_str = match unsafe { CStr::from_ptr(server_challenge).to_str() } {
        Ok(s) => s,
        Err(_) => {
            set_error_message(out_error, ERR_INVALID_UTF8_CHALLENGE);
            return ERROR_CODE;
        }
    };

    let verifier = proton_srp::RPGPVerifier::default();

    let client = match SRPAuth::new(
        &verifier,
        &password_str,
        4,
        salt_str,
        modulus_str,
        challenge_str,
    ) {
        Ok(c) => c,
        Err(e) => {
            set_error_message(out_error, &format!("{ERR_CREATE_SRP_CLIENT} {e}"));
            return ERROR_CODE;
        }
    };

    match client.generate_proofs() {
        Ok(proof_result) => {
            let proof_b64: SRPProofB64 = proof_result.into();

            let client_ephemeral = match CString::new(proof_b64.client_ephemeral) {
                Ok(s) => s.into_raw(),
                Err(_) => {
                    set_error_message(out_error, ERR_CONVERT_CLIENT_EPHEMERAL);
                    return ERROR_CODE;
                }
            };

            let client_proof = match CString::new(proof_b64.client_proof) {
                Ok(s) => s.into_raw(),
                Err(_) => {
                    set_error_message(out_error, ERR_CONVERT_CLIENT_PROOF);
                    return ERROR_CODE;
                }
            };

            let expected_server_proof = match CString::new(proof_b64.expected_server_proof) {
                Ok(s) => s.into_raw(),
                Err(_) => {
                    set_error_message(out_error, ERR_CONVERT_EXPECTED_SERVER_PROOF);
                    return ERROR_CODE;
                }
            };

            // nosem: rust.lang.security.unsafe-usage.unsafe-usage
            unsafe {
                (*out_proof).client_ephemeral = client_ephemeral;
                (*out_proof).client_proof = client_proof;
                (*out_proof).expected_server_proof = expected_server_proof;
            }

            0
        }
        Err(e) => {
            set_error_message(out_error, &format!("{ERR_GENERATE_PROOFS} {e}"));
            ERROR_CODE
        }
    }
}

fn set_error_message(out_error: *mut *mut c_char, message: &str) {
    if !out_error.is_null() {
        if let Ok(c_string) = CString::new(message) {
            // nosem: rust.lang.security.unsafe-usage.unsafe-usage
            unsafe {
                *out_error = c_string.into_raw();
            }
        }
    }
}

/// # Safety
/// The pointer s must either be null or a valid pointer returned from CString::into_raw().
/// This function takes ownership of the C string and frees its memory.
// nosem: rust.lang.security.unsafe-usage.unsafe-usage
#[unsafe(no_mangle)]
pub unsafe extern "C" fn free_c_string(s: *mut c_char) {
    if !s.is_null() {
        // nosem: rust.lang.security.unsafe-usage.unsafe-usage
        let _ = unsafe { CString::from_raw(s) };
    }
}

/// # Safety
/// The pointer proof must either be null or a valid pointer to a CSRPProof structure.
/// All string pointers within the CSRPProof must either be null or valid pointers
/// returned from CString::into_raw(). This function takes ownership and frees all memory.
// nosem: rust.lang.security.unsafe-usage.unsafe-usage
#[unsafe(no_mangle)]
pub unsafe extern "C" fn free_proof(proof: *mut CSRPProof) {
    if !proof.is_null() {
        // nosem: rust.lang.security.unsafe-usage.unsafe-usage
        unsafe {
            if !(*proof).client_ephemeral.is_null() {
                let _ = CString::from_raw((*proof).client_ephemeral);
            }
            if !(*proof).client_proof.is_null() {
                let _ = CString::from_raw((*proof).client_proof);
            }
            if !(*proof).expected_server_proof.is_null() {
                let _ = CString::from_raw((*proof).expected_server_proof);
            }
        }
    }
}