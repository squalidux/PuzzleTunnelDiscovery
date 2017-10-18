#ifndef OSR_GEOMETRY_H
#define OSR_GEOMETRY_H

#define GLM_FORCE_RADIANS
#include <glm/glm.hpp>
#include <glm/gtc/matrix_transform.hpp>

namespace osr {
struct Vertex {
    glm::vec3 position;
    glm::vec3 color;
};
}

#endif /* end of include guard: GEOMETRY_H */
