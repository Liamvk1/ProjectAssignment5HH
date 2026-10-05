package za.ac.up.cos790;

import org.junit.jupiter.api.Test;
import za.ac.up.cos790.domain.DomainRegistry;

import static org.junit.jupiter.api.Assertions.*;
import static org.junit.jupiter.api.Assertions.assertThrows;

/**
 * Tests for the stub-detection utility in {@link DomainRegistry} (Item 8).
 *
 * <p>The detection mechanism works by checking for the presence of the
 * {@code HYFLEX_STUB} sentinel field, which is declared only in the API stub
 * {@code AbstractClasses.ProblemDomain} (see {@code java/src/stubs/java/}).
 * When the real CHeSC jars are on the classpath, this field is absent and
 * {@code isStub} returns {@code false}.
 */
class DomainRegistryStubTest {

    /**
     * {@code isStub} must return a boolean without throwing for registered domains.
     *
     * <p>The specific value depends on whether real CHeSC jars are present:
     * {@code true} when only stubs are available; {@code false} when real jars are present.
     * This test asserts the method does not crash, not the specific value.
     */
    @Test
    void isStubReturnsWithoutException() {
        // The result depends on the build configuration.
        // With real CHeSC jars in lib/hyflex/: false.
        // With API stubs only: true.
        // Either outcome is correct; the test just asserts no exception is thrown.
        boolean result = DomainRegistry.isStub("SAT");
        // Verify the result matches what we can detect about the classpath.
        try {
            AbstractClasses.ProblemDomain.class.getField("HYFLEX_STUB");
            // HYFLEX_STUB field found, so stubs are in use.
            assertTrue(result, "isStub must return true when HYFLEX_STUB field is present.");
        } catch (NoSuchFieldException e) {
            // HYFLEX_STUB field absent, so real jars are in use.
            assertFalse(result, "isStub must return false when HYFLEX_STUB field is absent.");
        }
    }

    /**
     * {@code isStub} must throw {@code IllegalArgumentException} for unknown domain names,
     * consistent with the behaviour of {@code DomainRegistry.get()}.
     */
    @Test
    void isStubThrowsForUnknownDomain() {
        assertThrows(IllegalArgumentException.class,
                () -> DomainRegistry.isStub("NonExistentDomain"),
                "isStub must reject an unknown domain name.");
    }
}
