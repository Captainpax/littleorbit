import java.nio.file.Files;
import java.nio.file.Path;
import java.security.Key;
import java.security.KeyStore;
import java.security.MessageDigest;
import java.security.PrivateKey;
import java.security.cert.Certificate;
import java.util.Arrays;
import java.util.HexFormat;

public final class SignerCertificateVerifier {
    private SignerCertificateVerifier() {}

    private static char[] secret(Path path, String label) throws Exception {
        String value = Files.readString(path).strip();
        if (value.isEmpty() || value.indexOf('\n') >= 0 || value.indexOf('\r') >= 0) {
            throw new IllegalArgumentException(label + " must contain one non-empty line");
        }
        return value.toCharArray();
    }

    public static void main(String[] arguments) throws Exception {
        if (arguments.length != 1) {
            throw new IllegalArgumentException("one secret directory is required");
        }
        Path root = Path.of(arguments[0]);
        String alias = Files.readString(root.resolve("key-alias")).strip();
        if (!alias.matches("[A-Za-z0-9._-]{1,100}")) {
            throw new IllegalArgumentException("key alias is unsafe");
        }
        char[] storePassword = secret(root.resolve("store-password"), "store password");
        char[] keyPassword = secret(root.resolve("key-password"), "key password");
        try {
            KeyStore store = KeyStore.getInstance("PKCS12");
            try (var input = Files.newInputStream(root.resolve("release.p12"))) {
                store.load(input, storePassword);
            }
            Key key = store.getKey(alias, keyPassword);
            if (!(key instanceof PrivateKey)) {
                throw new IllegalArgumentException("signer alias is not a private key entry");
            }
            Certificate certificate = store.getCertificate(alias);
            if (certificate == null) {
                throw new IllegalArgumentException("signer certificate is missing");
            }
            byte[] digest = MessageDigest.getInstance("SHA-256").digest(certificate.getEncoded());
            System.out.println(HexFormat.of().formatHex(digest));
        } finally {
            Arrays.fill(storePassword, '\0');
            Arrays.fill(keyPassword, '\0');
        }
    }
}
