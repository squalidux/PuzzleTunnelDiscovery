#include "geometry.h"
#include "options.h"

int main(int argc, char* argv[])
{
	Options opt(argc, argv);
	// Use opt.get_input_stream() instead of Options object for
	// orthogonality
	MazeBoundary wall(opt.get_input_stream());
	MazeBoundary stick(opt.get_input_stream());

	for (auto wallid : wall.irange()) {
		for(auto stickid : stick.irange()) {
			Obstacle obs;
			obs.construct(wall.get_prim(wallid),
				    stick.get_prim(stickid),
				    stick.get_center());
			Eigen::MatrixXd V;
			Eigen::MatrixXi F;
			obs.build_VF(V, F);
			opt.write_geo("wall-"+
				      std::to_string(wallid)+
				      "-stick-"+
				      std::to_string(stickid),
				      V,
				      F);
		}
	}
	return 0;
}