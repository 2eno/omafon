# kotlinx.serialization: generierte Serializer behalten
-keepattributes *Annotation*, InnerClasses
-dontnote kotlinx.serialization.**
-keepclassmembers @kotlinx.serialization.Serializable class de.omafon.companion.** {
    *** Companion;
    kotlinx.serialization.KSerializer serializer(...);
}
-keep,includedescriptorclasses class de.omafon.companion.**$$serializer { *; }
# OkHttp
-dontwarn okhttp3.internal.platform.**
-dontwarn org.conscrypt.**
-dontwarn org.bouncycastle.**
-dontwarn org.openjsse.**
