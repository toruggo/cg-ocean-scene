### Computação Gráfica – Projeto 1

#### Objetivo:
Desenvolver um programa que apresente uma janela envolvendo diferentes
objetos, cores e transformações geométricas, conforme abaixo.

#### Requisitos:

1.  Devem ser exibidos 5 ou mais objetos de cores diferentes (pelo menos 2
deles devem ser 3D). Repetições de um mesmo objeto contarão apenas
um, mesmo que tenham pequenas variações. Por exemplo, várias nuvens
iguais ou modeladas a partir de números diferentes de círculos, contará
apenas um objeto. Idem para várias estrelas, por exemplo.

2. Os objetos devem ser composições de primitivas simples diferentes das
vistas em aula. Em outras palavras, um objeto não pode ser apenas um
triângulo (pirâmide), quadrado (cubo) e círculo (esfera). Estrelas, cataventos, bonecos, etc. são exemplos de objetos válidos. Os objetos não
podem ser importados de modelos prontos; eles devem ser criados por
vocês.

3.  Cada objeto deve ter sua própria matriz de transformação composta pelas
transformações geométricas primárias.

4. As transformações escala, rotação e translação devem ser aplicadas, cada
uma em um objeto diferente.

5. Usar teclado para aplicar translação em pelo menos um objeto.

6. Usar teclado para aplicar escala em pelo menos um objeto.

7. Usar teclado para aplicar rotação em pelo menos um objeto.

8. O programa deve ter um objetivo bem definido, ou seja, os objetos e
transformações devem fazer sentido para a cena.

9. O usuário deve poder visualizar a malha poligonal quando quiser. Caso ele
aperte ‘p’, as malhas dos objetos devem ser exibidas (caso estejam ocultas)
ou ocultadas (caso estejam sendo exibidas).

10. Neste trabalho, NÃO devem ser utilizadas texturas, movimentação de
câmera e efeitos de iluminação. Esses serão temas cobertos pelos
próximos trabalhos.

#### Outras informações importantes:

3. Pode-se utilizar, inclusive, outras linguagens de programação, desde que
utilize apenas bibliotecas do OpenGL e do sistema de janelas. O uso de
outras bibliotecas gráficas não será aceito.

4. Devem ser utilizadas apenas funções do pipeline moderno. No OpenGL, isso
significa que as seguintes funções são obsoletas (deprecated) e não podem
ser utilizadas: glRotate, glTranslate, glScale, glVertex, glColor, glLight,
glMaterial, glBegin, glEnd, glMatrix, glMatrixMode, glLoadIdentity,
glPushMatrix, glPopMatrix, glRect, glBitmap, glAphaFunc, glNewList,
glDisplayList, glPushAttrib, glPopAttrib, glVertexPointer, glColorPointer,
glTexCoordPointer, glNormalPointer, glMatrixMode, glCal.